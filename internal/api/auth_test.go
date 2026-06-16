package api

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/openautonomyx/platform/internal/store"
)

func TestRequiredPerm(t *testing.T) {
	cases := []struct {
		method, path string
		want         perm
	}{
		{"GET", "/healthz", permPublic},
		{"GET", "/", permPublic},
		{"GET", "/metrics", permPublic},
		{"GET", "/v1/models", permConsumer},
		{"GET", "/v1/metrics", permConsumer},
		{"POST", "/v1/models/loan-approval/execute", permConsumer},
		{"POST", "/v1/models", permAuthor},
		{"POST", "/v1/agents", permAuthor},
		{"PUT", "/v1/policies/large-loan-review", permAuthor},
		{"POST", "/v1/reviews/run_1/resolve", permAuthor},
	}
	for _, c := range cases {
		r := httptest.NewRequest(c.method, c.path, nil)
		if got := requiredPerm(r); got != c.want {
			t.Errorf("requiredPerm(%s %s) = %d, want %d", c.method, c.path, got, c.want)
		}
	}
}

func TestAuthEnforcement(t *testing.T) {
	st := store.New()
	st.RegisterAgent(store.Agent{ID: "boss", Roles: []string{"author"}}, "test")
	st.RegisterAgent(store.Agent{ID: "alice", Roles: []string{"consumer"}}, "test")
	s := &Server{cfg: Config{AccessMode: accessEnforce}, store: st}

	ok := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) })
	h := s.agentMW(s.authMW(ok))

	do := func(method, path, agent string) int {
		req := httptest.NewRequest(method, path, nil)
		if agent != "" {
			req.Header.Set("X-Agent", agent)
		}
		rr := httptest.NewRecorder()
		h.ServeHTTP(rr, req)
		return rr.Code
	}

	tests := []struct {
		name           string
		method, path   string
		agent          string
		wantStatusCode int
	}{
		{"public is open", "GET", "/healthz", "", http.StatusOK},
		{"consumer needs identity", "POST", "/v1/models/loan-approval/execute", "", http.StatusUnauthorized},
		{"identified consumer ok", "POST", "/v1/models/loan-approval/execute", "alice", http.StatusOK},
		{"reads need identity", "GET", "/v1/models", "", http.StatusUnauthorized},
		{"author route: anon", "POST", "/v1/models", "", http.StatusUnauthorized},
		{"author route: consumer forbidden", "POST", "/v1/models", "alice", http.StatusForbidden},
		{"author route: author ok", "POST", "/v1/models", "boss", http.StatusOK},
	}
	for _, tt := range tests {
		if got := do(tt.method, tt.path, tt.agent); got != tt.wantStatusCode {
			t.Errorf("%s: %s %s as %q = %d, want %d", tt.name, tt.method, tt.path, tt.agent, got, tt.wantStatusCode)
		}
	}
}

func TestAuthOpenModePassThrough(t *testing.T) {
	s := &Server{cfg: Config{AccessMode: accessOpen}, store: store.New()}
	ok := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) })
	h := s.agentMW(s.authMW(ok))

	// In open mode even an author-only route with no identity is allowed.
	req := httptest.NewRequest(http.MethodPost, "/v1/models", nil)
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Errorf("open mode should pass through, got %d", rr.Code)
	}
}
