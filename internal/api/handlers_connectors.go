package api

import (
	"context"
	"net/http"
	"time"

	"github.com/openautonomyx/platform/internal/fabric"
)

func (s *Server) fabGet(id string) (fabric.Connector, bool) {
	if s.fab == nil {
		return nil, false
	}
	return s.fab.Get(id)
}

// handleListConnectors lists data-fabric connectors and their configuration
// status (Decision Service Composition / all-source intelligence).
func (s *Server) handleListConnectors(w http.ResponseWriter, r *http.Request) {
	var statuses []fabric.Status
	if s.fab != nil {
		for _, c := range s.fab.List() {
			statuses = append(statuses, c.Status())
		}
	}
	writeJSON(w, http.StatusOK, map[string]any{"count": len(statuses), "connectors": statuses})
}

// handleAuthorizeConnector returns the OAuth authorization URL a user visits to
// grant the connector access with fine-grained scopes.
func (s *Server) handleAuthorizeConnector(w http.ResponseWriter, r *http.Request) {
	c, ok := s.fabGet(r.PathValue("id"))
	if !ok {
		writeError(w, r, http.StatusNotFound, "connector not found")
		return
	}
	fb, ok := c.(*fabric.Facebook)
	if !ok {
		writeError(w, r, http.StatusBadRequest, "connector does not support OAuth authorization")
		return
	}
	state := r.URL.Query().Get("state")
	if state == "" {
		state = "metakube"
	}
	u, err := fb.AuthorizationURL(state)
	if err != nil {
		writeError(w, r, http.StatusConflict, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"authorizationUrl": u})
}

type fetchRequest struct {
	ObjectID string `json:"objectId"`
}

// handleFetchConnector pulls a signal from a connector (e.g. Facebook comments).
// Requires the connector to be configured with credentials.
func (s *Server) handleFetchConnector(w http.ResponseWriter, r *http.Request) {
	c, ok := s.fabGet(r.PathValue("id"))
	if !ok {
		writeError(w, r, http.StatusNotFound, "connector not found")
		return
	}
	fb, ok := c.(*fabric.Facebook)
	if !ok {
		writeError(w, r, http.StatusBadRequest, "connector does not support fetch")
		return
	}
	if !fb.Configured() {
		writeError(w, r, http.StatusServiceUnavailable, "connector not configured: supply credentials via FACEBOOK_* environment variables")
		return
	}
	var req fetchRequest
	if err := decodeJSON(w, r, &req); err != nil {
		writeError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 12*time.Second)
	defer cancel()
	comments, err := fb.FetchComments(ctx, req.ObjectID)
	if err != nil {
		writeError(w, r, http.StatusBadGateway, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"connector": "facebook", "count": len(comments), "comments": comments})
}
