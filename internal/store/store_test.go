package store

import (
	"testing"

	"github.com/openautonomyx/platform/internal/engine"
)

func approveRun(model string) *Run {
	return &Run{
		ModelID: model, ModelVersion: "1.0.0", Source: "test",
		Status:  StatusFinal,
		Outcome: engine.Outcome{Decision: "APPROVE", RiskScore: 80, Confidence: 0.9},
	}
}

func TestAddAndGetRun(t *testing.T) {
	s := New()
	r := s.AddRun(approveRun("loan-approval"))
	if r.ID == "" {
		t.Fatal("AddRun should assign an ID")
	}
	got, ok := s.GetRun(r.ID)
	if !ok || got.ModelID != "loan-approval" {
		t.Fatalf("GetRun failed: %+v ok=%v", got, ok)
	}
	if len(s.ListRuns(0)) != 1 {
		t.Errorf("expected 1 run, got %d", len(s.ListRuns(0)))
	}
	// Every run also appends a DECISION_EXECUTED audit entry.
	audit := s.ListAudit(0)
	if len(audit) != 1 || audit[0].Action != "DECISION_EXECUTED" {
		t.Errorf("expected DECISION_EXECUTED audit entry, got %+v", audit)
	}
}

func TestReviewLifecycle(t *testing.T) {
	s := New()
	r := approveRun("loan-approval")
	r.Status = StatusPendingReview
	r.Outcome.Decision = "REVIEW"
	s.AddRun(r)

	if len(s.PendingReviews()) != 1 {
		t.Fatalf("expected 1 pending review")
	}

	// Resolving with a human override flips the decision and flags overridden.
	resolved, err := s.ResolveReview(r.ID, ReviewResult{Reviewer: "alice", Decision: "APPROVE"})
	if err != nil {
		t.Fatalf("ResolveReview error: %v", err)
	}
	if resolved.Status != StatusResolved || resolved.Review == nil || !resolved.Review.Overridden {
		t.Errorf("expected resolved+overridden, got %+v", resolved.Review)
	}
	if len(s.PendingReviews()) != 0 {
		t.Errorf("expected no pending reviews after resolve")
	}

	// Resolving again or an unknown run errors.
	if _, err := s.ResolveReview(r.ID, ReviewResult{Decision: "APPROVE"}); err == nil {
		t.Error("expected error resolving an already-resolved run")
	}
	if _, err := s.ResolveReview("missing", ReviewResult{Decision: "APPROVE"}); err == nil {
		t.Error("expected error resolving a missing run")
	}
	if _, err := s.ResolveReview(r.ID, ReviewResult{Decision: "MAYBE"}); err == nil {
		t.Error("expected error for invalid review decision")
	}
}

func TestPoliciesAndGovernance(t *testing.T) {
	s := New()
	if len(s.Policies()) == 0 {
		t.Fatal("expected seeded default policies")
	}

	// large-loan-review is enabled by default at 50000.
	oc := engine.Outcome{Decision: "APPROVE", Confidence: 0.9}
	applied := s.ApplyGovernance("loan-approval", map[string]any{"loanAmount": 90000.0}, &oc)
	if oc.Decision != "REVIEW" {
		t.Errorf("large loan should be downgraded to REVIEW, got %s", oc.Decision)
	}
	if len(applied) == 0 || applied[0] != "large-loan-review" {
		t.Errorf("expected large-loan-review applied, got %v", applied)
	}

	// Disabling the policy stops the downgrade.
	if _, err := s.UpdatePolicy("large-loan-review", false, nil, "admin"); err != nil {
		t.Fatalf("UpdatePolicy error: %v", err)
	}
	oc2 := engine.Outcome{Decision: "APPROVE", Confidence: 0.9}
	if applied := s.ApplyGovernance("loan-approval", map[string]any{"loanAmount": 90000.0}, &oc2); len(applied) != 0 {
		t.Errorf("disabled policy should not apply, got %v", applied)
	}
	if _, err := s.UpdatePolicy("nope", true, nil, "admin"); err == nil {
		t.Error("expected error updating unknown policy")
	}
}

func TestAgents(t *testing.T) {
	s := New()
	if _, err := s.RegisterAgent(Agent{ID: ""}, "x"); err == nil {
		t.Error("expected error registering agent without id")
	}
	a, err := s.RegisterAgent(Agent{ID: "bot", Name: "Bot", Roles: []string{"author"}}, "admin")
	if err != nil || !a.Registered {
		t.Fatalf("RegisterAgent failed: %+v err=%v", a, err)
	}
	s.TouchAgent("bot")
	s.TouchAgent("bot")
	got, ok := s.GetAgent("bot")
	if !ok || got.Requests != 2 {
		t.Errorf("expected 2 requests for bot, got %+v ok=%v", got, ok)
	}
	// TouchAgent auto-creates an unregistered record.
	s.TouchAgent("seen-only")
	if g, ok := s.GetAgent("seen-only"); !ok || g.Registered {
		t.Errorf("seen-only should exist as unregistered, got %+v ok=%v", g, ok)
	}
	if len(s.ListAgents()) != 2 {
		t.Errorf("expected 2 agents, got %d", len(s.ListAgents()))
	}
}
