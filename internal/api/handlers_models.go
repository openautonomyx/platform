package api

import (
	"net/http"
	"time"

	"github.com/openautonomyx/platform/internal/engine"
	"github.com/openautonomyx/platform/internal/store"
)

type modelSummary struct {
	ID          string    `json:"id"`
	Name        string    `json:"name"`
	Version     string    `json:"version"`
	Description string    `json:"description,omitempty"`
	Tags        []string  `json:"tags,omitempty"`
	Inputs      int       `json:"inputs"`
	CreatedAt   time.Time `json:"createdAt"`
}

// handleListModels lists registered decision models (Decision Modeling).
func (s *Server) handleListModels(w http.ResponseWriter, r *http.Request) {
	models := s.cat.List()
	summaries := make([]modelSummary, 0, len(models))
	for _, m := range models {
		summaries = append(summaries, modelSummary{
			ID: m.ID, Name: m.Name, Version: m.Version, Description: m.Description,
			Tags: m.Tags, Inputs: len(m.Inputs), CreatedAt: m.CreatedAt,
		})
	}
	writeJSON(w, http.StatusOK, map[string]any{"count": len(summaries), "models": summaries})
}

// handleGetModel returns a full model definition.
func (s *Server) handleGetModel(w http.ResponseWriter, r *http.Request) {
	m, ok := s.cat.Get(r.PathValue("id"))
	if !ok {
		writeError(w, r, http.StatusNotFound, "model not found")
		return
	}
	writeJSON(w, http.StatusOK, m)
}

// handleCreateModel registers or replaces a decision model (Decision Modeling).
func (s *Server) handleCreateModel(w http.ResponseWriter, r *http.Request) {
	var m engine.Model
	if err := decodeJSON(w, r, &m); err != nil {
		writeError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	if _, err := s.cat.Put(&m); err != nil {
		writeError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	s.store.AppendAudit(&store.AuditEntry{
		Actor:   actor(r),
		Action:  "MODEL_REGISTERED",
		Subject: m.ID,
		Details: map[string]any{"version": m.Version, "name": m.Name},
	})
	w.Header().Set("Location", "/v1/models/"+m.ID)
	writeJSON(w, http.StatusCreated, m)
}

// handleModelVersions returns the version history of a model.
func (s *Server) handleModelVersions(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	if _, ok := s.cat.Get(id); !ok {
		writeError(w, r, http.StatusNotFound, "model not found")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"modelId": id, "versions": s.cat.Versions(id)})
}

type serviceDescriptor struct {
	ID          string               `json:"id"`
	Name        string               `json:"name"`
	Version     string               `json:"version"`
	Description string               `json:"description,omitempty"`
	Tags        []string             `json:"tags,omitempty"`
	Status      string               `json:"status"`
	Method      string               `json:"method"`
	Endpoint    string               `json:"endpoint"`
	InputSchema []engine.InputField  `json:"inputSchema"`
	Outputs     []engine.OutputField `json:"outputs,omitempty"`
}

// handleListServices exposes models as discoverable, composable decision
// services with their I/O schema (Decision Service Composition).
func (s *Server) handleListServices(w http.ResponseWriter, r *http.Request) {
	models := s.cat.List()
	services := make([]serviceDescriptor, 0, len(models))
	for _, m := range models {
		services = append(services, serviceDescriptor{
			ID: m.ID, Name: m.Name, Version: m.Version, Description: m.Description,
			Tags: m.Tags, Status: "available", Method: http.MethodPost,
			Endpoint:    "/v1/models/" + m.ID + "/execute",
			InputSchema: m.Inputs, Outputs: m.Outputs,
		})
	}
	writeJSON(w, http.StatusOK, map[string]any{"count": len(services), "services": services})
}

type executeRequest struct {
	Inputs       map[string]any `json:"inputs"`
	IncludeTrace *bool          `json:"includeTrace,omitempty"`
}

// handleExecute evaluates a model against supplied inputs, applies governance
// policies, records the run and routes REVIEW outcomes to the queue (Decision
// Execution + Governance + Collaboration).
func (s *Server) handleExecute(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	compiled, ok := s.cat.Compiled(id)
	if !ok {
		writeError(w, r, http.StatusNotFound, "model not found")
		return
	}
	var req executeRequest
	if err := decodeJSON(w, r, &req); err != nil {
		writeError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	if len(req.Inputs) == 0 {
		writeError(w, r, http.StatusBadRequest, "field 'inputs' is required and must be a non-empty object")
		return
	}

	result, err := compiled.Evaluate(req.Inputs)
	if err != nil {
		writeError(w, r, http.StatusUnprocessableEntity, err.Error())
		return
	}

	model, _ := s.cat.Get(id)
	applied := s.store.ApplyGovernance(id, req.Inputs, &result.Outcome)

	status := store.StatusFinal
	if result.Outcome.Decision == string(engine.Review) {
		status = store.StatusPendingReview
	}
	run := &store.Run{
		ModelID: id, ModelVersion: model.Version, Inputs: req.Inputs,
		Outcome: result.Outcome, Status: status, Source: "api", Policies: applied,
	}
	if s.tracesRetained() {
		trace := result.Trace
		run.Trace = &trace
	}
	s.store.AddRun(run)

	resp := *run
	if req.IncludeTrace != nil && !*req.IncludeTrace {
		resp.Trace = nil
	}
	writeJSON(w, http.StatusOK, resp)
}

// tracesRetained reports whether the retain-full-trace governance policy is on.
func (s *Server) tracesRetained() bool {
	if p, ok := s.store.Policy("retain-full-trace"); ok {
		return p.Enabled
	}
	return true
}

// actor returns the identity to attribute an action to, as resolved by
// agentMW from the request's X-Agent/X-Actor headers.
func actor(r *http.Request) string {
	return agentFrom(r.Context())
}
