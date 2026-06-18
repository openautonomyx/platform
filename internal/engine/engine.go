package engine

import (
	"fmt"
	"math"
	"sort"
	"strings"

	"github.com/openautonomyx/platform/internal/expr"
)

// defaultScoreVar is the context key the scorecard writes to when a model does
// not specify Scorecard.Output.
const defaultScoreVar = "riskScore"

// Compiled is a model whose expressions have been parsed and validated, ready
// for repeated, concurrent evaluation. Compiled values are immutable and safe
// for use by multiple goroutines.
type Compiled struct {
	Model    *Model
	scoreVar string

	derivations []compiledDerivation
	knockouts   []compiledRule
	factors     []compiledFactor
	rows        []compiledRow
}

type compiledDerivation struct {
	key  string
	expr *expr.Expr
}

type compiledRule struct {
	id, code, reason string
	when             *expr.Expr
}

type compiledFactor struct {
	id, reason string
	points     float64
	when       *expr.Expr
}

type compiledRow struct {
	id, decision, tier, reason string
	when                       *expr.Expr
	set                        map[string]any
}

// Compile validates a model and pre-parses every expression it contains. Any
// malformed expression is reported here rather than at evaluation time.
func Compile(m *Model) (*Compiled, error) {
	if err := Validate(m); err != nil {
		return nil, err
	}
	c := &Compiled{Model: m, scoreVar: defaultScoreVar}
	if m.Scorecard != nil && m.Scorecard.Output != "" {
		c.scoreVar = m.Scorecard.Output
	}

	for _, d := range m.Derivations {
		e, err := expr.Parse(d.Expr)
		if err != nil {
			return nil, fmt.Errorf("derivation %q: %w", d.Key, err)
		}
		c.derivations = append(c.derivations, compiledDerivation{key: d.Key, expr: e})
	}
	for _, k := range m.Knockouts {
		e, err := expr.Parse(k.When)
		if err != nil {
			return nil, fmt.Errorf("knockout %q: %w", k.ID, err)
		}
		c.knockouts = append(c.knockouts, compiledRule{id: k.ID, code: k.Code, reason: k.Reason, when: e})
	}
	if m.Scorecard != nil {
		for _, f := range m.Scorecard.Factors {
			e, err := expr.Parse(f.When)
			if err != nil {
				return nil, fmt.Errorf("scorecard factor %q: %w", f.ID, err)
			}
			c.factors = append(c.factors, compiledFactor{id: f.ID, reason: f.Reason, points: f.Points, when: e})
		}
	}
	if m.Decision != nil {
		for _, r := range m.Decision.Rules {
			e, err := expr.Parse(r.When)
			if err != nil {
				return nil, fmt.Errorf("decision row %q: %w", r.ID, err)
			}
			c.rows = append(c.rows, compiledRow{
				id: r.ID, decision: r.Decision, tier: r.Tier, reason: r.Reason, when: e, set: r.Set,
			})
		}
	}
	return c, nil
}

// Validate checks a model's structural integrity without compiling expressions.
func Validate(m *Model) error {
	if m == nil {
		return fmt.Errorf("model is nil")
	}
	if strings.TrimSpace(m.ID) == "" {
		return fmt.Errorf("model id is required")
	}
	if strings.TrimSpace(m.Name) == "" {
		return fmt.Errorf("model name is required")
	}
	if strings.TrimSpace(m.Version) == "" {
		return fmt.Errorf("model version is required")
	}
	if len(m.Inputs) == 0 {
		return fmt.Errorf("model must declare at least one input")
	}
	seen := map[string]bool{}
	for _, in := range m.Inputs {
		if in.Key == "" {
			return fmt.Errorf("input key is required")
		}
		if seen[in.Key] {
			return fmt.Errorf("duplicate input key %q", in.Key)
		}
		seen[in.Key] = true
		switch in.Type {
		case "number", "string", "boolean":
		default:
			return fmt.Errorf("input %q: unsupported type %q", in.Key, in.Type)
		}
	}
	if m.Decision == nil || len(m.Decision.Rules) == 0 {
		return fmt.Errorf("model must declare a decision table with at least one rule")
	}
	for _, r := range m.Decision.Rules {
		switch Decision(r.Decision) {
		case Approve, Review, Decline:
		default:
			return fmt.Errorf("decision row %q: invalid decision %q", r.ID, r.Decision)
		}
	}
	return nil
}

// Evaluate runs the compiled model against the supplied inputs and returns the
// outcome together with a full trace. It never mutates the caller's map.
func (c *Compiled) Evaluate(inputs map[string]any) (*Result, error) {
	env, err := c.buildContext(inputs)
	if err != nil {
		return nil, err
	}

	res := &Result{Trace: Trace{}}
	menv := expr.MapEnv(env)

	// Stage 1: derivations.
	if len(c.derivations) > 0 {
		derived := map[string]any{}
		for _, d := range c.derivations {
			v, err := d.expr.Eval(menv)
			if err != nil {
				return nil, fmt.Errorf("derivation %q: %w", d.key, err)
			}
			env[d.key] = v
			derived[d.key] = v
		}
		res.Trace.Stages = append(res.Trace.Stages, Stage{
			Name:    "derivations",
			Summary: fmt.Sprintf("computed %d derived value(s)", len(derived)),
			Detail:  derived,
		})
	}

	// Stage 2: knockouts. Any firing knockout forces a DECLINE.
	var koReasons []ReasonCode
	var koFired []string
	for _, k := range c.knockouts {
		fired, err := k.when.EvalBool(menv)
		if err != nil {
			return nil, fmt.Errorf("knockout %q: %w", k.id, err)
		}
		if fired {
			koFired = append(koFired, k.id)
			koReasons = append(koReasons, ReasonCode{
				Code:        codeOf(k.code, k.id),
				Description: orDefault(k.reason, "knockout rule fired"),
			})
		}
	}
	res.Trace.Stages = append(res.Trace.Stages, Stage{
		Name:    "knockouts",
		Summary: fmt.Sprintf("%d of %d knockout rule(s) fired", len(koFired), len(c.knockouts)),
		Fired:   koFired,
	})
	if len(koFired) > 0 {
		res.Trace.Context = env
		res.Outcome = Outcome{
			Decision:    string(Decline),
			RiskScore:   0,
			Tier:        "KO",
			Confidence:  0.98,
			ReasonCodes: koReasons,
			Explanation: "Declined by knockout policy: " + joinReasons(koReasons),
		}
		return res, nil
	}

	// Stage 3: scorecard.
	score := 0.0
	var scoreReasons []ReasonCode
	if c.Model.Scorecard != nil {
		score = c.Model.Scorecard.Base
		var fired []string
		breakdown := map[string]any{"base": c.Model.Scorecard.Base}
		for _, f := range c.factors {
			ok, err := f.when.EvalBool(menv)
			if err != nil {
				return nil, fmt.Errorf("scorecard factor %q: %w", f.id, err)
			}
			if ok {
				score += f.points
				fired = append(fired, f.id)
				breakdown[f.id] = f.points
				scoreReasons = append(scoreReasons, ReasonCode{
					Code:        codeOf("", f.id),
					Description: orDefault(f.reason, "factor applied"),
					Impact:      f.points,
				})
			}
		}
		score = clamp(score, c.Model.Scorecard.Min, c.Model.Scorecard.Max)
		env[c.scoreVar] = score
		breakdown["total"] = score
		res.Trace.Stages = append(res.Trace.Stages, Stage{
			Name:    "scorecard",
			Summary: fmt.Sprintf("%s = %.1f (%d factor(s) fired)", c.scoreVar, score, len(fired)),
			Fired:   fired,
			Detail:  breakdown,
		})
	}

	// Stage 4: decision table (FIRST hit).
	var matched *compiledRow
	for i := range c.rows {
		ok, err := c.rows[i].when.EvalBool(menv)
		if err != nil {
			return nil, fmt.Errorf("decision row %q: %w", c.rows[i].id, err)
		}
		if ok {
			matched = &c.rows[i]
			break
		}
	}
	if matched == nil {
		return nil, fmt.Errorf("decision table produced no match (no default rule)")
	}
	outputs := map[string]any{}
	for k, v := range matched.set {
		outputs[k] = v
		env[k] = v
	}
	res.Trace.Stages = append(res.Trace.Stages, Stage{
		Name:    "decisionTable",
		Summary: fmt.Sprintf("matched rule %q -> %s", matched.id, matched.decision),
		Fired:   []string{matched.id},
		Detail:  map[string]any{"decision": matched.decision, "tier": matched.tier},
	})

	// Assemble outcome.
	sortReasons(scoreReasons)
	if matched.reason != "" {
		scoreReasons = append([]ReasonCode{{Code: codeOf("", matched.id), Description: matched.reason}}, scoreReasons...)
	}
	res.Trace.Context = env
	res.Outcome = Outcome{
		Decision:    matched.decision,
		RiskScore:   round1(score),
		Tier:        matched.tier,
		Confidence:  confidenceFor(score, c.Model.Scorecard),
		ReasonCodes: topReasons(scoreReasons, 5),
		Outputs:     nonEmpty(outputs),
		Explanation: explain(matched.decision, score, scoreReasons),
	}
	return res, nil
}

// buildContext validates inputs against the model and returns a fresh context.
func (c *Compiled) buildContext(inputs map[string]any) (map[string]any, error) {
	env := make(map[string]any, len(inputs)+8)
	for _, in := range c.Model.Inputs {
		raw, present := inputs[in.Key]
		if !present {
			if in.Required {
				return nil, fmt.Errorf("missing required input %q", in.Key)
			}
			continue
		}
		v, err := coerceInput(in, raw)
		if err != nil {
			return nil, err
		}
		env[in.Key] = v
	}
	// Pass through any additional inputs the caller supplied so models can be
	// extended without rejecting unknown fields.
	declared := map[string]bool{}
	for _, in := range c.Model.Inputs {
		declared[in.Key] = true
	}
	for k, v := range inputs {
		if !declared[k] {
			env[k] = v
		}
	}
	return env, nil
}

func coerceInput(in InputField, raw any) (any, error) {
	switch in.Type {
	case "number":
		f, ok := toFloat(raw)
		if !ok {
			return nil, fmt.Errorf("input %q must be a number", in.Key)
		}
		if in.Min != nil && f < *in.Min {
			return nil, fmt.Errorf("input %q must be >= %g", in.Key, *in.Min)
		}
		if in.Max != nil && f > *in.Max {
			return nil, fmt.Errorf("input %q must be <= %g", in.Key, *in.Max)
		}
		return f, nil
	case "string":
		s, ok := raw.(string)
		if !ok {
			return nil, fmt.Errorf("input %q must be a string", in.Key)
		}
		if len(in.Enum) > 0 && !contains(in.Enum, s) {
			return nil, fmt.Errorf("input %q must be one of %s", in.Key, strings.Join(in.Enum, ", "))
		}
		return s, nil
	case "boolean":
		b, ok := raw.(bool)
		if !ok {
			return nil, fmt.Errorf("input %q must be a boolean", in.Key)
		}
		return b, nil
	}
	return nil, fmt.Errorf("input %q: unsupported type %q", in.Key, in.Type)
}

// confidenceFor derives a confidence score from how far the risk score sits
// from the neutral midpoint of the scorecard's range. Extreme scores are more
// confident than borderline ones.
func confidenceFor(score float64, sc *Scorecard) float64 {
	if sc == nil {
		return 0.75
	}
	mid := (sc.Min + sc.Max) / 2
	half := (sc.Max - sc.Min) / 2
	if half <= 0 {
		return 0.75
	}
	margin := math.Abs(score-mid) / half // 0..1
	return round2(clamp(0.55+0.44*margin, 0.55, 0.99))
}

func explain(decision string, score float64, reasons []ReasonCode) string {
	var b strings.Builder
	switch Decision(decision) {
	case Approve:
		fmt.Fprintf(&b, "Approved with a risk score of %.0f. ", score)
	case Review:
		fmt.Fprintf(&b, "Routed to human review with a borderline risk score of %.0f. ", score)
	case Decline:
		fmt.Fprintf(&b, "Declined with a risk score of %.0f. ", score)
	default:
		fmt.Fprintf(&b, "Decision %s with a risk score of %.0f. ", decision, score)
	}
	if top := topReasons(reasons, 2); len(top) > 0 {
		b.WriteString("Primary drivers: " + joinReasons(top) + ".")
	}
	return strings.TrimSpace(b.String())
}

func sortReasons(rs []ReasonCode) {
	sort.SliceStable(rs, func(i, j int) bool {
		return math.Abs(rs[i].Impact) > math.Abs(rs[j].Impact)
	})
}

func topReasons(rs []ReasonCode, n int) []ReasonCode {
	if len(rs) <= n {
		return rs
	}
	return rs[:n]
}

func joinReasons(rs []ReasonCode) string {
	parts := make([]string, 0, len(rs))
	for _, r := range rs {
		parts = append(parts, r.Description)
	}
	return strings.Join(parts, "; ")
}

// ---- small helpers ----

func clamp(v, lo, hi float64) float64 {
	if hi > lo {
		if v < lo {
			return lo
		}
		if v > hi {
			return hi
		}
	}
	return v
}

func toFloat(v any) (float64, bool) {
	switch n := v.(type) {
	case float64:
		return n, true
	case float32:
		return float64(n), true
	case int:
		return float64(n), true
	case int64:
		return float64(n), true
	}
	return 0, false
}

func contains(ss []string, s string) bool {
	for _, x := range ss {
		if x == s {
			return true
		}
	}
	return false
}

func codeOf(code, id string) string {
	if code != "" {
		return code
	}
	return strings.ToUpper(id)
}

func orDefault(s, def string) string {
	if strings.TrimSpace(s) == "" {
		return def
	}
	return s
}

func nonEmpty(m map[string]any) map[string]any {
	if len(m) == 0 {
		return nil
	}
	return m
}

func round1(f float64) float64 { return math.Round(f*10) / 10 }
func round2(f float64) float64 { return math.Round(f*100) / 100 }
