package engine

import "testing"

func testModel() *Model {
	f := func(v float64) *float64 { return &v }
	return &Model{
		ID:      "loan",
		Name:    "Loan Approval",
		Version: "1.0.0",
		Inputs: []InputField{
			{Key: "creditScore", Type: "number", Required: true, Min: f(300), Max: f(850)},
			{Key: "annualIncome", Type: "number", Required: true, Min: f(0)},
			{Key: "monthlyDebt", Type: "number", Required: true, Min: f(0)},
			{Key: "loanAmount", Type: "number", Required: true, Min: f(0)},
			{Key: "age", Type: "number", Required: true},
		},
		Derivations: []Derivation{
			{Key: "monthlyIncome", Expr: "annualIncome / 12"},
			{Key: "dti", Expr: "monthlyDebt / monthlyIncome"},
		},
		Knockouts: []Rule{
			{ID: "ko_age", When: "age < 18", Reason: "Below minimum age"},
			{ID: "ko_score", When: "creditScore < 500", Reason: "Credit score too low"},
			{ID: "ko_dti", When: "dti > 0.6", Reason: "Debt-to-income too high"},
		},
		Scorecard: &Scorecard{
			Base: 40, Min: 0, Max: 100,
			Factors: []ScoreFactor{
				{ID: "excellent_credit", When: "creditScore >= 750", Points: 30, Reason: "Excellent credit"},
				{ID: "good_credit", When: "creditScore >= 660 && creditScore < 750", Points: 18, Reason: "Good credit"},
				{ID: "low_dti", When: "dti <= 0.25", Points: 20, Reason: "Low debt burden"},
				{ID: "high_dti", When: "dti > 0.45", Points: -20, Reason: "Elevated debt burden"},
			},
		},
		Decision: &DecisionTable{
			HitPolicy: "FIRST",
			Rules: []DecisionRow{
				{ID: "approve", When: "riskScore >= 75", Decision: "APPROVE", Tier: "A"},
				{ID: "review", When: "riskScore >= 55", Decision: "REVIEW", Tier: "B"},
				{ID: "decline", When: "true", Decision: "DECLINE", Tier: "C"},
			},
		},
	}
}

func eval(t *testing.T, c *Compiled, in map[string]any) *Result {
	t.Helper()
	r, err := c.Evaluate(in)
	if err != nil {
		t.Fatalf("Evaluate error: %v", err)
	}
	return r
}

func TestEvaluateDecisions(t *testing.T) {
	c, err := Compile(testModel())
	if err != nil {
		t.Fatalf("Compile error: %v", err)
	}

	// Strong applicant -> APPROVE (base 40 + 30 excellent + 20 low dti = 90).
	r := eval(t, c, map[string]any{
		"creditScore": 780.0, "annualIncome": 120000.0, "monthlyDebt": 1500.0,
		"loanAmount": 20000.0, "age": 35.0,
	})
	if r.Outcome.Decision != string(Approve) {
		t.Fatalf("strong applicant: got %s, want APPROVE (score=%.1f)", r.Outcome.Decision, r.Outcome.RiskScore)
	}
	if r.Outcome.RiskScore != 90 {
		t.Errorf("expected score 90, got %.1f", r.Outcome.RiskScore)
	}

	// Borderline applicant -> REVIEW (base 40 + 18 good credit = 58).
	r = eval(t, c, map[string]any{
		"creditScore": 700.0, "annualIncome": 90000.0, "monthlyDebt": 2400.0,
		"loanAmount": 15000.0, "age": 40.0,
	})
	if r.Outcome.Decision != string(Review) {
		t.Fatalf("borderline applicant: got %s, want REVIEW (score=%.1f)", r.Outcome.Decision, r.Outcome.RiskScore)
	}

	// Weak applicant -> DECLINE (base 40 + 18 good - 20 high dti = 38).
	r = eval(t, c, map[string]any{
		"creditScore": 690.0, "annualIncome": 40000.0, "monthlyDebt": 1700.0,
		"loanAmount": 25000.0, "age": 30.0,
	})
	if r.Outcome.Decision != string(Decline) {
		t.Fatalf("weak applicant: got %s, want DECLINE (score=%.1f)", r.Outcome.Decision, r.Outcome.RiskScore)
	}

	// Knockout -> DECLINE with tier KO regardless of score.
	r = eval(t, c, map[string]any{
		"creditScore": 480.0, "annualIncome": 120000.0, "monthlyDebt": 100.0,
		"loanAmount": 5000.0, "age": 45.0,
	})
	if r.Outcome.Decision != string(Decline) || r.Outcome.Tier != "KO" {
		t.Fatalf("knockout: got %s/%s, want DECLINE/KO", r.Outcome.Decision, r.Outcome.Tier)
	}
	if len(r.Outcome.ReasonCodes) == 0 {
		t.Error("knockout should produce reason codes")
	}
}

func TestEvaluateValidation(t *testing.T) {
	c, _ := Compile(testModel())

	if _, err := c.Evaluate(map[string]any{"creditScore": 700.0}); err == nil {
		t.Error("expected error for missing required inputs")
	}
	if _, err := c.Evaluate(map[string]any{
		"creditScore": 900.0, "annualIncome": 50000.0, "monthlyDebt": 500.0,
		"loanAmount": 10000.0, "age": 30.0,
	}); err == nil {
		t.Error("expected error for creditScore above max")
	}
}

func TestEvaluateProducesTrace(t *testing.T) {
	c, _ := Compile(testModel())
	r := eval(t, c, map[string]any{
		"creditScore": 780.0, "annualIncome": 120000.0, "monthlyDebt": 1500.0,
		"loanAmount": 20000.0, "age": 35.0,
	})
	names := map[string]bool{}
	for _, s := range r.Trace.Stages {
		names[s.Name] = true
	}
	for _, want := range []string{"derivations", "knockouts", "scorecard", "decisionTable"} {
		if !names[want] {
			t.Errorf("trace missing stage %q", want)
		}
	}
	if r.Trace.Context["dti"] == nil {
		t.Error("trace context should include derived dti")
	}
	if r.Outcome.Confidence <= 0 || r.Outcome.Confidence > 1 {
		t.Errorf("confidence out of range: %v", r.Outcome.Confidence)
	}
}

func TestCompileRejectsBadModel(t *testing.T) {
	bad := testModel()
	bad.Knockouts[0].When = "age <"
	if _, err := Compile(bad); err == nil {
		t.Error("expected compile error for malformed expression")
	}

	noTable := testModel()
	noTable.Decision = nil
	if _, err := Compile(noTable); err == nil {
		t.Error("expected validation error for missing decision table")
	}
}
