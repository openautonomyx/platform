package expr

import "testing"

func TestEval(t *testing.T) {
	env := MapEnv{
		"creditScore": 720.0,
		"dti":         0.28,
		"income":      84000.0,
		"purpose":     "home",
		"vip":         true,
	}
	cases := []struct {
		src  string
		want any
	}{
		{"1 + 2 * 3", 7.0},
		{"(1 + 2) * 3", 9.0},
		{"10 / 4", 2.5},
		{"10 % 3", 1.0},
		{"-5 + 2", -3.0},
		{"creditScore >= 700", true},
		{"creditScore < 700", false},
		{"dti <= 0.3 && creditScore >= 680", true},
		{"dti > 0.3 || creditScore >= 680", true},
		{"!vip", false},
		{"purpose == 'home'", true},
		{"purpose != 'auto'", true},
		{"income / 12 > 5000", true},
		{"min(3, 7, 2)", 2.0},
		{"max(3, 7, 2)", 7.0},
		{"abs(-4)", 4.0},
		{"round(2.6)", 3.0},
		{"floor(2.9)", 2.0},
		{"ceil(2.1)", 3.0},
		{"creditScore >= 750", false},
		{"vip && creditScore >= 700", true},
	}
	for _, c := range cases {
		e, err := Parse(c.src)
		if err != nil {
			t.Fatalf("Parse(%q) error: %v", c.src, err)
		}
		got, err := e.Eval(env)
		if err != nil {
			t.Fatalf("Eval(%q) error: %v", c.src, err)
		}
		if got != c.want {
			t.Errorf("Eval(%q) = %v (%T), want %v (%T)", c.src, got, got, c.want, c.want)
		}
	}
}

func TestEvalBoolShortCircuit(t *testing.T) {
	// Right side references an unknown identifier; short-circuit must avoid it.
	e := MustParse("false && missing > 1")
	got, err := e.EvalBool(MapEnv{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != false {
		t.Errorf("got %v, want false", got)
	}

	e2 := MustParse("true || missing > 1")
	got2, err := e2.EvalBool(MapEnv{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got2 != true {
		t.Errorf("got %v, want true", got2)
	}
}

func TestErrors(t *testing.T) {
	cases := []string{
		"1 +",          // dangling operator
		"(1 + 2",       // unbalanced paren
		"1 2",          // trailing token
		"'unterminated", // bad string
		"1 / 0",        // division by zero (eval error)
		"unknownVar",   // unknown identifier (eval error)
		"true + 1",     // type error
	}
	for _, src := range cases {
		e, err := Parse(src)
		if err != nil {
			continue // parse error is an acceptable failure
		}
		if _, err := e.Eval(MapEnv{}); err == nil {
			t.Errorf("expected error for %q, got none", src)
		}
	}
}

func TestEvalNumber(t *testing.T) {
	e := MustParse("base + bonus * 2")
	got, err := e.EvalNumber(MapEnv{"base": 50.0, "bonus": 10.0})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != 70.0 {
		t.Errorf("got %v, want 70", got)
	}
}

func TestDottedPath(t *testing.T) {
	env := MapEnv{"applicant": map[string]any{"score": 800.0}}
	e := MustParse("applicant.score >= 750")
	got, err := e.EvalBool(env)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !got {
		t.Errorf("got %v, want true", got)
	}
}
