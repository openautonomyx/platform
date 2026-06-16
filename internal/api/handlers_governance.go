package api

import (
	"net/http"
	"strings"

	"github.com/openautonomyx/platform/internal/store"
)

// handleListReviews lists decisions awaiting a human verdict (Decision
// Collaboration / human-in-the-loop).
func (s *Server) handleListReviews(w http.ResponseWriter, r *http.Request) {
	pending := s.store.PendingReviews()
	out := make([]store.Run, 0, len(pending))
	for _, run := range pending {
		v := *run
		v.Trace = nil
		out = append(out, v)
	}
	writeJSON(w, http.StatusOK, map[string]any{"count": len(out), "reviews": out})
}

type resolveRequest struct {
	Reviewer string `json:"reviewer"`
	Decision string `json:"decision"`
	Comment  string `json:"comment,omitempty"`
}

// handleResolveReview applies a human decision to a queued run, recording any
// override of the engine's recommendation for learning and governance.
func (s *Server) handleResolveReview(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	var req resolveRequest
	if err := decodeJSON(w, r, &req); err != nil {
		writeError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	if req.Reviewer == "" {
		req.Reviewer = actor(r)
	}
	run, err := s.store.ResolveReview(id, store.ReviewResult{
		Reviewer: req.Reviewer, Decision: strings.ToUpper(req.Decision), Comment: req.Comment,
	})
	if err != nil {
		writeError(w, r, statusForResolveError(err), err.Error())
		return
	}
	writeJSON(w, http.StatusOK, run)
}

func statusForResolveError(err error) int {
	msg := err.Error()
	switch {
	case strings.Contains(msg, "not found"):
		return http.StatusNotFound
	case strings.Contains(msg, "not pending"):
		return http.StatusConflict
	default:
		return http.StatusBadRequest
	}
}

// handleListAudit returns the append-only governance audit log (Decision
// Governance).
func (s *Server) handleListAudit(w http.ResponseWriter, r *http.Request) {
	entries := s.store.ListAudit(queryInt(r, "limit", 100))
	writeJSON(w, http.StatusOK, map[string]any{"count": len(entries), "entries": entries})
}

// handleListPolicies lists governance policies (Decision Governance).
func (s *Server) handleListPolicies(w http.ResponseWriter, r *http.Request) {
	policies := s.store.Policies()
	writeJSON(w, http.StatusOK, map[string]any{"count": len(policies), "policies": policies})
}

type updatePolicyRequest struct {
	Enabled bool     `json:"enabled"`
	Value   *float64 `json:"value,omitempty"`
}

// handleUpdatePolicy toggles or retunes a governance policy.
func (s *Server) handleUpdatePolicy(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	var req updatePolicyRequest
	if err := decodeJSON(w, r, &req); err != nil {
		writeError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	p, err := s.store.UpdatePolicy(id, req.Enabled, req.Value, actor(r))
	if err != nil {
		writeError(w, r, http.StatusNotFound, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, p)
}
