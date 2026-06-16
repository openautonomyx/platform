package catalog

import (
	"testing"

	"github.com/openautonomyx/platform/internal/engine"
)

func TestSeedAndLookup(t *testing.T) {
	c := New()
	Seed(c)
	if c.Len() != 2 {
		t.Fatalf("expected 2 seeded models, got %d", c.Len())
	}
	m, ok := c.Get("loan-approval")
	if !ok || m.Name == "" {
		t.Fatalf("loan-approval not found")
	}
	if _, ok := c.Compiled("loan-approval"); !ok {
		t.Error("compiled loan-approval not found")
	}
	if len(c.List()) != 2 {
		t.Errorf("List should return 2 models")
	}
	if len(c.Versions("loan-approval")) == 0 {
		t.Error("expected version history for loan-approval")
	}
	if _, ok := c.Get("nope"); ok {
		t.Error("unexpected model found")
	}
}

func TestPutValidAndInvalid(t *testing.T) {
	c := New()
	valid := &engine.Model{
		ID: "t", Name: "T", Version: "1.0.0",
		Inputs:   []engine.InputField{{Key: "a", Type: "number"}},
		Decision: &engine.DecisionTable{Rules: []engine.DecisionRow{{ID: "r", When: "true", Decision: "APPROVE"}}},
	}
	if _, err := c.Put(valid); err != nil {
		t.Fatalf("Put(valid) error: %v", err)
	}
	if c.Len() != 1 {
		t.Errorf("expected 1 model after Put")
	}

	// Re-registering with a new version extends the version history.
	valid.Version = "1.1.0"
	if _, err := c.Put(valid); err != nil {
		t.Fatalf("Put(new version) error: %v", err)
	}
	if got := len(c.Versions("t")); got != 2 {
		t.Errorf("expected 2 versions, got %d", got)
	}

	// A model with a malformed rule expression is rejected at Put time.
	bad := &engine.Model{
		ID: "b", Name: "B", Version: "1.0.0",
		Inputs:    []engine.InputField{{Key: "a", Type: "number"}},
		Knockouts: []engine.Rule{{ID: "k", When: "a <"}},
		Decision:  &engine.DecisionTable{Rules: []engine.DecisionRow{{ID: "r", When: "true", Decision: "APPROVE"}}},
	}
	if _, err := c.Put(bad); err == nil {
		t.Error("expected Put(bad) to fail on malformed expression")
	}
}
