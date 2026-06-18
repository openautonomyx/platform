package store

import (
	"fmt"
	"time"
)

// Agent is a durable, first-class identity in the platform. Agents are the
// actors that execute and review decisions; persisting them and their activity
// is the basis for attribution, accountability and governance.
type Agent struct {
	ID          string    `json:"id"`
	Name        string    `json:"name,omitempty"`
	Description string    `json:"description,omitempty"`
	Roles       []string  `json:"roles,omitempty"`
	Registered  bool      `json:"registered"`
	Requests    int64     `json:"requests"`
	FirstSeen   time.Time `json:"firstSeen"`
	LastSeen    time.Time `json:"lastSeen"`
}

// RegisterAgent creates or updates a registered agent identity and records the
// registration in the audit log.
func (s *Store) RegisterAgent(a Agent, actor string) (*Agent, error) {
	if a.ID == "" {
		return nil, fmt.Errorf("agent id is required")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	now := time.Now().UTC()
	existing, ok := s.agents[a.ID]
	if !ok {
		existing = &Agent{ID: a.ID, FirstSeen: now, LastSeen: now}
		s.agents[a.ID] = existing
		s.agentOrder = append(s.agentOrder, a.ID)
	}
	existing.Name = a.Name
	existing.Description = a.Description
	existing.Roles = a.Roles
	existing.Registered = true
	s.appendAuditLocked(&AuditEntry{
		Actor:   actor,
		Action:  "AGENT_REGISTERED",
		Subject: a.ID,
		Details: map[string]any{"name": a.Name, "roles": a.Roles},
	})
	cp := *existing
	return &cp, nil
}

// TouchAgent records activity for an agent, auto-creating an unregistered
// record on first contact. It is cheap and safe to call on every request.
func (s *Store) TouchAgent(id string) {
	if id == "" {
		return
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	now := time.Now().UTC()
	a, ok := s.agents[id]
	if !ok {
		a = &Agent{ID: id, FirstSeen: now}
		s.agents[id] = a
		s.agentOrder = append(s.agentOrder, id)
	}
	a.Requests++
	a.LastSeen = now
}

// GetAgent returns an agent by ID.
func (s *Store) GetAgent(id string) (*Agent, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	a, ok := s.agents[id]
	if !ok {
		return nil, false
	}
	cp := *a
	return &cp, true
}

// ListAgents returns all known agents in first-seen order.
func (s *Store) ListAgents() []*Agent {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]*Agent, 0, len(s.agentOrder))
	for _, id := range s.agentOrder {
		cp := *s.agents[id]
		out = append(out, &cp)
	}
	return out
}
