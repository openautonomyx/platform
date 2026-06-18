// Package store provides MetaKube's in-memory, concurrency-safe operational
// state: the history of decision runs, an append-only audit log, the
// human-in-the-loop review queue and governance policies. State is bounded so a
// long-running process cannot grow without limit, which keeps the service
// stable under sustained load.
package store

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"sort"
	"sync"
	"time"

	"github.com/openautonomyx/platform/internal/engine"
)

const (
	maxRuns  = 5000
	maxAudit = 10000
)

// Run records a single decision execution.
type Run struct {
	ID           string         `json:"id"`
	ModelID      string         `json:"modelId"`
	ModelVersion string         `json:"modelVersion"`
	Inputs       map[string]any `json:"inputs"`
	Outcome      engine.Outcome `json:"outcome"`
	Trace        *engine.Trace  `json:"trace,omitempty"`
	Status       string         `json:"status"` // FINAL | PENDING_REVIEW | RESOLVED
	Source       string         `json:"source"` // api | simulation
	Policies     []string       `json:"appliedPolicies,omitempty"`
	CreatedAt    time.Time      `json:"createdAt"`
	Review       *ReviewResult  `json:"review,omitempty"`
}

// ReviewResult records a human decision on a queued run.
type ReviewResult struct {
	Reviewer   string    `json:"reviewer"`
	Decision   string    `json:"decision"`
	Comment    string    `json:"comment,omitempty"`
	Overridden bool      `json:"overridden"`
	ResolvedAt time.Time `json:"resolvedAt"`
}

// AuditEntry is one immutable record in the governance audit log.
type AuditEntry struct {
	ID        string         `json:"id"`
	Timestamp time.Time      `json:"timestamp"`
	Actor     string         `json:"actor"`
	Action    string         `json:"action"`
	Subject   string         `json:"subject"`
	Details   map[string]any `json:"details,omitempty"`
}

// Policy is a governance control that can influence decisions.
type Policy struct {
	ID          string    `json:"id"`
	Name        string    `json:"name"`
	Description string    `json:"description"`
	Enabled     bool      `json:"enabled"`
	Value       float64   `json:"value,omitempty"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

// Statuses.
const (
	StatusFinal         = "FINAL"
	StatusPendingReview = "PENDING_REVIEW"
	StatusResolved      = "RESOLVED"
)

// Store holds all operational state.
type Store struct {
	mu         sync.RWMutex
	runs       []*Run
	runIndex   map[string]*Run
	audit      []*AuditEntry
	policies   map[string]*Policy
	policyID   []string // stable ordering
	agents     map[string]*Agent
	agentOrder []string // stable ordering
}

// New returns a store seeded with default governance policies.
func New() *Store {
	s := &Store{
		runIndex: map[string]*Run{},
		policies: map[string]*Policy{},
		agents:   map[string]*Agent{},
	}
	for _, p := range defaultPolicies() {
		s.policies[p.ID] = p
		s.policyID = append(s.policyID, p.ID)
	}
	return s
}

func defaultPolicies() []*Policy {
	now := time.Now().UTC()
	return []*Policy{
		{ID: "large-loan-review", Name: "Large Loan Manual Review", Enabled: true, Value: 50000,
			Description: "Auto-approved loans above this amount (USD) are downgraded to manual review.", UpdatedAt: now},
		{ID: "min-confidence-review", Name: "Low-Confidence Manual Review", Enabled: false, Value: 0.6,
			Description: "Approvals with confidence below this threshold are downgraded to manual review.", UpdatedAt: now},
		{ID: "retain-full-trace", Name: "Retain Full Decision Trace", Enabled: true,
			Description: "Persist the complete evaluation trace for every decision for auditability.", UpdatedAt: now},
	}
}

// AddRun stores a run, assigning an ID if absent, and records an audit entry.
func (s *Store) AddRun(r *Run) *Run {
	s.mu.Lock()
	defer s.mu.Unlock()
	if r.ID == "" {
		r.ID = newID("run")
	}
	if r.CreatedAt.IsZero() {
		r.CreatedAt = time.Now().UTC()
	}
	s.runs = append(s.runs, r)
	s.runIndex[r.ID] = r
	if len(s.runs) > maxRuns {
		drop := s.runs[0]
		s.runs = s.runs[1:]
		delete(s.runIndex, drop.ID)
	}
	s.appendAuditLocked(&AuditEntry{
		Actor:   r.Source,
		Action:  "DECISION_EXECUTED",
		Subject: r.ID,
		Details: map[string]any{
			"modelId":  r.ModelID,
			"decision": r.Outcome.Decision,
			"score":    r.Outcome.RiskScore,
			"status":   r.Status,
		},
	})
	return r
}

// GetRun returns a run by ID.
func (s *Store) GetRun(id string) (*Run, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	r, ok := s.runIndex[id]
	return r, ok
}

// ListRuns returns up to limit runs, most recent first. limit <= 0 means all.
func (s *Store) ListRuns(limit int) []*Run {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return reverseRuns(s.runs, limit)
}

// PendingReviews returns runs awaiting a human decision, most recent first.
func (s *Store) PendingReviews() []*Run {
	s.mu.RLock()
	defer s.mu.RUnlock()
	var out []*Run
	for i := len(s.runs) - 1; i >= 0; i-- {
		if s.runs[i].Status == StatusPendingReview {
			out = append(out, s.runs[i])
		}
	}
	return out
}

// ResolveReview applies a human decision to a queued run.
func (s *Store) ResolveReview(id string, res ReviewResult) (*Run, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	r, ok := s.runIndex[id]
	if !ok {
		return nil, fmt.Errorf("run %q not found", id)
	}
	if r.Status != StatusPendingReview {
		return nil, fmt.Errorf("run %q is not pending review", id)
	}
	switch engine.Decision(res.Decision) {
	case engine.Approve, engine.Decline:
	default:
		return nil, fmt.Errorf("review decision must be APPROVE or DECLINE")
	}
	res.ResolvedAt = time.Now().UTC()
	res.Overridden = res.Decision != r.Outcome.Decision
	r.Review = &res
	r.Status = StatusResolved
	s.appendAuditLocked(&AuditEntry{
		Actor:   res.Reviewer,
		Action:  "REVIEW_RESOLVED",
		Subject: r.ID,
		Details: map[string]any{
			"humanDecision":  res.Decision,
			"engineDecision": r.Outcome.Decision,
			"overridden":     res.Overridden,
			"comment":        res.Comment,
		},
	})
	return r, nil
}

// AppendAudit adds an audit entry from outside the store (e.g. model changes).
func (s *Store) AppendAudit(e *AuditEntry) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.appendAuditLocked(e)
}

func (s *Store) appendAuditLocked(e *AuditEntry) {
	if e.ID == "" {
		e.ID = newID("evt")
	}
	if e.Timestamp.IsZero() {
		e.Timestamp = time.Now().UTC()
	}
	if e.Actor == "" {
		e.Actor = "system"
	}
	s.audit = append(s.audit, e)
	if len(s.audit) > maxAudit {
		s.audit = s.audit[1:]
	}
}

// ListAudit returns up to limit audit entries, most recent first.
func (s *Store) ListAudit(limit int) []*AuditEntry {
	s.mu.RLock()
	defer s.mu.RUnlock()
	n := len(s.audit)
	if limit <= 0 || limit > n {
		limit = n
	}
	out := make([]*AuditEntry, 0, limit)
	for i := n - 1; i >= 0 && len(out) < limit; i-- {
		out = append(out, s.audit[i])
	}
	return out
}

// Policies returns all governance policies in stable order.
func (s *Store) Policies() []*Policy {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]*Policy, 0, len(s.policyID))
	for _, id := range s.policyID {
		p := *s.policies[id]
		out = append(out, &p)
	}
	return out
}

// Policy returns a single policy by ID.
func (s *Store) Policy(id string) (*Policy, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	p, ok := s.policies[id]
	if !ok {
		return nil, false
	}
	cp := *p
	return &cp, true
}

// UpdatePolicy enables/disables a policy and optionally updates its value.
func (s *Store) UpdatePolicy(id string, enabled bool, value *float64, actor string) (*Policy, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	p, ok := s.policies[id]
	if !ok {
		return nil, fmt.Errorf("policy %q not found", id)
	}
	p.Enabled = enabled
	if value != nil {
		p.Value = *value
	}
	p.UpdatedAt = time.Now().UTC()
	s.appendAuditLocked(&AuditEntry{
		Actor:   actor,
		Action:  "POLICY_UPDATED",
		Subject: id,
		Details: map[string]any{"enabled": p.Enabled, "value": p.Value},
	})
	cp := *p
	return &cp, nil
}

// ApplyGovernance mutates an outcome according to enabled policies and returns
// the IDs of policies that took effect. This is where governance controls have
// teeth: they can downgrade an approval to a manual review.
func (s *Store) ApplyGovernance(modelID string, inputs map[string]any, oc *engine.Outcome) []string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	var applied []string

	if p := s.policies["large-loan-review"]; p != nil && p.Enabled && modelID == "loan-approval" {
		if amt, ok := inputs["loanAmount"].(float64); ok && amt > p.Value && oc.Decision == string(engine.Approve) {
			oc.Decision = string(engine.Review)
			oc.ReasonCodes = append([]engine.ReasonCode{{
				Code: "POLICY_LARGE_LOAN", Description: fmt.Sprintf("Loan amount exceeds $%.0f governance threshold; routed to manual review", p.Value),
			}}, oc.ReasonCodes...)
			oc.Explanation = "Governance policy override: large loan routed to manual review. " + oc.Explanation
			applied = append(applied, p.ID)
		}
	}

	if p := s.policies["min-confidence-review"]; p != nil && p.Enabled {
		if oc.Decision == string(engine.Approve) && oc.Confidence < p.Value {
			oc.Decision = string(engine.Review)
			oc.ReasonCodes = append([]engine.ReasonCode{{
				Code: "POLICY_LOW_CONFIDENCE", Description: fmt.Sprintf("Confidence %.2f below governance threshold %.2f; routed to manual review", oc.Confidence, p.Value),
			}}, oc.ReasonCodes...)
			applied = append(applied, p.ID)
		}
	}

	return applied
}

func reverseRuns(runs []*Run, limit int) []*Run {
	n := len(runs)
	if limit <= 0 || limit > n {
		limit = n
	}
	out := make([]*Run, 0, limit)
	for i := n - 1; i >= 0 && len(out) < limit; i-- {
		out = append(out, runs[i])
	}
	return out
}

// SortRunsByTime returns runs sorted ascending by CreatedAt (used by metrics).
func SortRunsByTime(runs []*Run) []*Run {
	out := append([]*Run(nil), runs...)
	sort.Slice(out, func(i, j int) bool { return out[i].CreatedAt.Before(out[j].CreatedAt) })
	return out
}

func newID(prefix string) string {
	var b [8]byte
	if _, err := rand.Read(b[:]); err != nil {
		// rand.Read essentially never fails; fall back to a timestamp.
		return fmt.Sprintf("%s_%d", prefix, time.Now().UnixNano())
	}
	return prefix + "_" + hex.EncodeToString(b[:])
}
