// Package engine implements MetaKube's decision engine: it compiles declarative
// decision models and executes them against input data, producing an auditable
// outcome plus a full explainability trace.
package engine

import "time"

// Decision is the categorical result of evaluating a decision model.
type Decision string

const (
	Approve Decision = "APPROVE"
	Review  Decision = "REVIEW"
	Decline Decision = "DECLINE"
)

// Model is a declarative, JSON-serializable decision model. A model is a small
// pipeline: validate inputs -> derive values -> apply knockouts -> score ->
// resolve a decision table -> assemble the outcome.
type Model struct {
	ID          string         `json:"id"`
	Name        string         `json:"name"`
	Version     string         `json:"version"`
	Description string         `json:"description,omitempty"`
	Tags        []string       `json:"tags,omitempty"`
	Inputs      []InputField   `json:"inputs"`
	Derivations []Derivation   `json:"derivations,omitempty"`
	Knockouts   []Rule         `json:"knockouts,omitempty"`
	Scorecard   *Scorecard     `json:"scorecard,omitempty"`
	Decision    *DecisionTable `json:"decisionTable,omitempty"`
	Outputs     []OutputField  `json:"outputs,omitempty"`
	CreatedAt   time.Time      `json:"createdAt"`
}

// InputField declares a model input and its validation constraints.
type InputField struct {
	Key      string   `json:"key"`
	Label    string   `json:"label,omitempty"`
	Type     string   `json:"type"` // number | string | boolean
	Required bool     `json:"required,omitempty"`
	Min      *float64 `json:"min,omitempty"`
	Max      *float64 `json:"max,omitempty"`
	Enum     []string `json:"enum,omitempty"`
	Example  any      `json:"example,omitempty"`
}

// Derivation computes an intermediate value from an expression and adds it to
// the evaluation context under Key.
type Derivation struct {
	Key   string `json:"key"`
	Label string `json:"label,omitempty"`
	Expr  string `json:"expr"`
}

// Rule is a named boolean predicate, used for knockouts.
type Rule struct {
	ID     string `json:"id"`
	When   string `json:"when"`
	Code   string `json:"code,omitempty"`
	Reason string `json:"reason,omitempty"`
}

// Scorecard accumulates points from factors whose conditions fire, producing a
// bounded numeric score added to the context under Output (default riskScore).
type Scorecard struct {
	Base    float64       `json:"base"`
	Min     float64       `json:"min"`
	Max     float64       `json:"max"`
	Output  string        `json:"output,omitempty"`
	Factors []ScoreFactor `json:"factors"`
}

// ScoreFactor contributes Points to the score when its condition fires.
type ScoreFactor struct {
	ID     string  `json:"id"`
	When   string  `json:"when"`
	Points float64 `json:"points"`
	Reason string  `json:"reason,omitempty"`
}

// DecisionTable maps the evaluation context to a final decision. Only the
// FIRST hit policy is currently supported (rows are evaluated top to bottom).
type DecisionTable struct {
	HitPolicy string        `json:"hitPolicy,omitempty"`
	Rules     []DecisionRow `json:"rules"`
}

// DecisionRow is a single decision-table rule.
type DecisionRow struct {
	ID       string         `json:"id"`
	When     string         `json:"when"`
	Decision string         `json:"decision"`
	Tier     string         `json:"tier,omitempty"`
	Reason   string         `json:"reason,omitempty"`
	Set      map[string]any `json:"set,omitempty"`
}

// OutputField documents an output the model produces.
type OutputField struct {
	Key   string `json:"key"`
	Label string `json:"label,omitempty"`
}

// ReasonCode is an explainability artifact: a coded factor that influenced the
// outcome, with the magnitude of its impact.
type ReasonCode struct {
	Code        string  `json:"code"`
	Description string  `json:"description"`
	Impact      float64 `json:"impact,omitempty"`
}

// Outcome is the result of evaluating a model.
type Outcome struct {
	Decision    string         `json:"decision"`
	RiskScore   float64        `json:"riskScore"`
	Tier        string         `json:"tier,omitempty"`
	Confidence  float64        `json:"confidence"`
	ReasonCodes []ReasonCode   `json:"reasonCodes"`
	Outputs     map[string]any `json:"outputs,omitempty"`
	Explanation string         `json:"explanation"`
}

// Stage records what happened in one phase of evaluation, for the audit trace.
type Stage struct {
	Name    string         `json:"name"`
	Summary string         `json:"summary,omitempty"`
	Fired   []string       `json:"fired,omitempty"`
	Detail  map[string]any `json:"detail,omitempty"`
}

// Trace is the full, replayable explanation of an evaluation.
type Trace struct {
	Stages  []Stage        `json:"stages"`
	Context map[string]any `json:"context"`
}

// Result bundles the outcome and trace returned by an evaluation.
type Result struct {
	Outcome Outcome `json:"outcome"`
	Trace   Trace   `json:"trace"`
}
