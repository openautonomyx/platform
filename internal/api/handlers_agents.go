package api

import (
	"net/http"

	"github.com/openautonomyx/platform/internal/store"
)

// handleListAgents lists durable agent identities and their activity.
func (s *Server) handleListAgents(w http.ResponseWriter, r *http.Request) {
	agents := s.store.ListAgents()
	writeJSON(w, http.StatusOK, map[string]any{"count": len(agents), "agents": agents})
}

// handleGetAgent returns a single agent identity.
func (s *Server) handleGetAgent(w http.ResponseWriter, r *http.Request) {
	a, ok := s.store.GetAgent(r.PathValue("id"))
	if !ok {
		writeError(w, r, http.StatusNotFound, "agent not found")
		return
	}
	writeJSON(w, http.StatusOK, a)
}

type registerAgentRequest struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	Description string   `json:"description"`
	Roles       []string `json:"roles"`
}

// handleRegisterAgent registers (or updates) a durable agent identity.
func (s *Server) handleRegisterAgent(w http.ResponseWriter, r *http.Request) {
	var req registerAgentRequest
	if err := decodeJSON(w, r, &req); err != nil {
		writeError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	a, err := s.store.RegisterAgent(store.Agent{
		ID: req.ID, Name: req.Name, Description: req.Description, Roles: req.Roles,
	}, actor(r))
	if err != nil {
		writeError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	w.Header().Set("Location", "/v1/agents/"+a.ID)
	writeJSON(w, http.StatusCreated, a)
}
