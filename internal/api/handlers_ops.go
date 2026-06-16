package api

import (
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/openautonomyx/platform/internal/version"
)

func (s *Server) handleHealthz(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok"})
}

func (s *Server) handleReadyz(w http.ResponseWriter, r *http.Request) {
	if !s.ready.Load() || s.cat.Len() == 0 {
		writeJSON(w, http.StatusServiceUnavailable, map[string]any{"status": "not ready"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ready", "models": s.cat.Len()})
}

func (s *Server) handleVersion(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, version.Get())
}

// handleRoot describes the platform and its capabilities, acting as a
// machine-readable service index.
func (s *Server) handleRoot(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		writeError(w, r, http.StatusNotFound, "not found")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"service":     "MetaKube",
		"description": "Kubernetes-native Decision Intelligence Platform",
		"version":     version.Get().Version,
		"uptime":      time.Since(s.started).Round(time.Second).String(),
		"accessMode":  s.cfg.AccessMode,
		"capabilities": map[string]string{
			"decisionModeling":           "POST /v1/models, GET /v1/models, GET /v1/models/{id}",
			"decisionExecution":          "POST /v1/models/{id}/execute, POST /v1/models/{id}/simulate",
			"decisionServiceComposition": "GET /v1/services",
			"decisionMonitoring":         "GET /v1/runs, GET /v1/runs/{id}, GET /v1/metrics",
			"decisionCollaboration":      "GET /v1/reviews, POST /v1/reviews/{id}/resolve",
			"decisionGovernance":         "GET /v1/audit, GET /v1/policies, PUT /v1/policies/{id}",
			"agentRegistry":              "GET /v1/agents, POST /v1/agents, GET /v1/agents/{id}",
			"agentTools":                 "GET /v1/tools",
		},
		"ops": map[string]string{
			"health":     "GET /healthz",
			"readiness":  "GET /readyz",
			"version":    "GET /version",
			"prometheus": "GET /metrics",
		},
	})
}

// handlePrometheus exposes a minimal Prometheus text exposition for ops
// monitoring (liveness counters, queue depth, build info).
func (s *Server) handlePrometheus(w http.ResponseWriter, r *http.Request) {
	runs := s.store.ListRuns(0)
	counts := map[string]int{"APPROVE": 0, "REVIEW": 0, "DECLINE": 0}
	for _, run := range runs {
		counts[run.Outcome.Decision]++
	}
	pending := len(s.store.PendingReviews())
	info := version.Get()

	var b strings.Builder
	b.WriteString("# HELP metakube_build_info Build information.\n")
	b.WriteString("# TYPE metakube_build_info gauge\n")
	fmt.Fprintf(&b, "metakube_build_info{version=%q,commit=%q,go=%q} 1\n", info.Version, info.Commit, info.GoVersion)

	b.WriteString("# HELP metakube_models Number of registered decision models.\n")
	b.WriteString("# TYPE metakube_models gauge\n")
	fmt.Fprintf(&b, "metakube_models %d\n", s.cat.Len())

	b.WriteString("# HELP metakube_decisions_total Decisions executed since start, by outcome.\n")
	b.WriteString("# TYPE metakube_decisions_total counter\n")
	for _, d := range []string{"APPROVE", "REVIEW", "DECLINE"} {
		fmt.Fprintf(&b, "metakube_decisions_total{decision=%q} %d\n", d, counts[d])
	}

	b.WriteString("# HELP metakube_pending_reviews Decisions awaiting human review.\n")
	b.WriteString("# TYPE metakube_pending_reviews gauge\n")
	fmt.Fprintf(&b, "metakube_pending_reviews %d\n", pending)

	b.WriteString("# HELP metakube_uptime_seconds Process uptime in seconds.\n")
	b.WriteString("# TYPE metakube_uptime_seconds gauge\n")
	fmt.Fprintf(&b, "metakube_uptime_seconds %d\n", int(time.Since(s.started).Seconds()))

	w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(b.String()))
}
