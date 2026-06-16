package api

import (
	"net/http"
	"time"

	"github.com/openautonomyx/platform/internal/store"
)

// handleListRuns returns recorded decision runs, filterable by model, decision
// and status (Decision Monitoring). Traces are omitted from the list view to
// keep payloads small; fetch a single run for its full trace.
func (s *Server) handleListRuns(w http.ResponseWriter, r *http.Request) {
	limit := queryInt(r, "limit", 50)
	modelFilter := r.URL.Query().Get("model")
	decisionFilter := r.URL.Query().Get("decision")
	statusFilter := r.URL.Query().Get("status")

	all := s.store.ListRuns(0)
	out := make([]store.Run, 0, limit)
	for _, run := range all {
		if modelFilter != "" && run.ModelID != modelFilter {
			continue
		}
		if decisionFilter != "" && run.Outcome.Decision != decisionFilter {
			continue
		}
		if statusFilter != "" && run.Status != statusFilter {
			continue
		}
		v := *run
		v.Trace = nil
		out = append(out, v)
		if len(out) >= limit {
			break
		}
	}
	writeJSON(w, http.StatusOK, map[string]any{"count": len(out), "runs": out})
}

// handleGetRun returns a single run including its full evaluation trace.
func (s *Server) handleGetRun(w http.ResponseWriter, r *http.Request) {
	run, ok := s.store.GetRun(r.PathValue("id"))
	if !ok {
		writeError(w, r, http.StatusNotFound, "run not found")
		return
	}
	writeJSON(w, http.StatusOK, run)
}

// handleMetrics returns aggregated decision-quality metrics (Decision
// Monitoring).
func (s *Server) handleMetrics(w http.ResponseWriter, r *http.Request) {
	m := computeMetrics(s.store.ListRuns(0), time.Now().UTC())
	writeJSON(w, http.StatusOK, m)
}
