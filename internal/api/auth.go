package api

import (
	"net/http"
	"strings"
)

// perm is the access level a request requires.
type perm int

const (
	permPublic   perm = iota // open to anyone (ops endpoints)
	permConsumer             // any identified agent (execute + read)
	permAuthor               // an agent with the author (or *) role
)

// Access modes.
const (
	accessOpen    = "open"    // no enforcement (default)
	accessEnforce = "enforce" // RBAC is enforced
)

// requiredPerm classifies a request into the access level it needs. This is the
// single "bridge" every agent request passes through.
func requiredPerm(r *http.Request) perm {
	p := r.URL.Path
	switch p {
	case "/", "/healthz", "/readyz", "/version", "/metrics":
		return permPublic
	}
	// Authoring / governance mutations require the author role.
	switch {
	case r.Method == http.MethodPost && p == "/v1/models":
		return permAuthor
	case r.Method == http.MethodPost && p == "/v1/agents":
		return permAuthor
	case r.Method == http.MethodPut && strings.HasPrefix(p, "/v1/policies/"):
		return permAuthor
	case r.Method == http.MethodPost && strings.HasPrefix(p, "/v1/reviews/"):
		// Resolving a queued decision is a privileged reviewer action.
		return permAuthor
	}
	// Everything else under the API (execute, simulate, reads) is consumer level.
	return permConsumer
}

// authMW enforces role-based access when the server is in enforce mode. In the
// default open mode it is a pass-through, so existing clients are unaffected.
func (s *Server) authMW(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.EqualFold(s.cfg.AccessMode, accessEnforce) {
			next.ServeHTTP(w, r)
			return
		}
		agent := agentFrom(r.Context())
		switch requiredPerm(r) {
		case permPublic:
			// always allowed
		case permConsumer:
			if agent == defaultAgent {
				writeError(w, r, http.StatusUnauthorized, "authentication required: provide an X-Agent header")
				return
			}
		case permAuthor:
			if agent == defaultAgent {
				writeError(w, r, http.StatusUnauthorized, "authentication required: provide an X-Agent header")
				return
			}
			if !s.agentHasRole(agent, "author", "*") {
				writeError(w, r, http.StatusForbidden, "forbidden: the 'author' role is required for this action")
				return
			}
		}
		next.ServeHTTP(w, r)
	})
}

// agentHasRole reports whether the registered agent holds any of the given
// roles. The wildcard role "*" grants everything.
func (s *Server) agentHasRole(id string, roles ...string) bool {
	a, ok := s.store.GetAgent(id)
	if !ok {
		return false
	}
	for _, have := range a.Roles {
		if have == "*" {
			return true
		}
		for _, want := range roles {
			if have == want {
				return true
			}
		}
	}
	return false
}
