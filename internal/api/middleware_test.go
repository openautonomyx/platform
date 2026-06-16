package api

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestAgentMW(t *testing.T) {
	var seen string
	h := agentMW(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = agentFrom(r.Context())
		w.WriteHeader(http.StatusOK)
	}))

	cases := []struct {
		name   string
		header map[string]string
		want   string
	}{
		{"x-agent", map[string]string{"X-Agent": "risk-agent-1"}, "risk-agent-1"},
		{"x-actor fallback", map[string]string{"X-Actor": "ops-bob"}, "ops-bob"},
		{"x-agent wins", map[string]string{"X-Agent": "a", "X-Actor": "b"}, "a"},
		{"default", nil, "anonymous"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, "/", nil)
			for k, v := range c.header {
				req.Header.Set(k, v)
			}
			rr := httptest.NewRecorder()
			h.ServeHTTP(rr, req)
			if seen != c.want {
				t.Errorf("context agent = %q, want %q", seen, c.want)
			}
			if got := rr.Header().Get("X-Agent"); got != c.want {
				t.Errorf("response X-Agent = %q, want %q", got, c.want)
			}
		})
	}
}

func TestAgentFromEmptyContext(t *testing.T) {
	if got := agentFrom(context.Background()); got != "anonymous" {
		t.Errorf("agentFrom(empty) = %q, want anonymous", got)
	}
}
