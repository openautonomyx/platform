// Package expr implements a small, safe, dependency-free expression language
// used to express decision rules declaratively (knockout conditions, scorecard
// factors and decision-table predicates).
//
// The language supports:
//   - numbers (float64), strings ('a' or "a"), booleans (true/false) and null
//   - identifiers resolved from an Env, including dotted paths (a.b.c)
//   - arithmetic:        + - * / %   (numbers)
//   - comparison:        < <= > >=   (numbers or strings)
//   - equality:          == !=
//   - logical:           && || !     (booleans, short-circuit)
//   - grouping:          ( )
//   - builtin functions: min max abs round floor ceil
//
// Expressions are parsed once and may be evaluated many times against different
// environments, which makes them cheap to reuse inside the decision engine.
package expr

import (
	"fmt"
	"math"
	"strings"
)

// Value is the runtime value of an expression: float64, bool, string or nil.
type Value = any

// Env resolves identifiers to values during evaluation.
type Env interface {
	Lookup(name string) (Value, bool)
}

// MapEnv is a simple map-backed Env that also supports dotted path lookups
// into nested map[string]any values.
type MapEnv map[string]any

// Lookup implements Env.
func (m MapEnv) Lookup(name string) (Value, bool) {
	if v, ok := m[name]; ok {
		return normalize(v), true
	}
	if strings.Contains(name, ".") {
		var cur any = map[string]any(m)
		for _, p := range strings.Split(name, ".") {
			mm, ok := cur.(map[string]any)
			if !ok {
				return nil, false
			}
			cur, ok = mm[p]
			if !ok {
				return nil, false
			}
		}
		return normalize(cur), true
	}
	return nil, false
}

// normalize coerces numeric kinds to float64 so the evaluator only deals with
// a single numeric representation.
func normalize(v any) any {
	switch n := v.(type) {
	case int:
		return float64(n)
	case int8:
		return float64(n)
	case int16:
		return float64(n)
	case int32:
		return float64(n)
	case int64:
		return float64(n)
	case uint:
		return float64(n)
	case uint32:
		return float64(n)
	case uint64:
		return float64(n)
	case float32:
		return float64(n)
	default:
		return v
	}
}

// Expr is a parsed, reusable expression.
type Expr struct {
	root node
	src  string
}

// Source returns the original expression text.
func (e *Expr) Source() string { return e.src }

// Parse compiles src into a reusable Expr.
func Parse(src string) (*Expr, error) {
	toks, err := lex(src)
	if err != nil {
		return nil, fmt.Errorf("expr %q: %w", src, err)
	}
	p := &parser{toks: toks}
	n, err := p.parseExpr(0)
	if err != nil {
		return nil, fmt.Errorf("expr %q: %w", src, err)
	}
	if p.peek().kind != tEOF {
		return nil, fmt.Errorf("expr %q: unexpected trailing token %q", src, p.peek().text)
	}
	return &Expr{root: n, src: src}, nil
}

// MustParse is like Parse but panics on error. Intended for trusted, embedded
// expressions such as seed models.
func MustParse(src string) *Expr {
	e, err := Parse(src)
	if err != nil {
		panic(err)
	}
	return e
}

// Eval evaluates the expression against env.
func (e *Expr) Eval(env Env) (Value, error) { return e.root.eval(env) }

// EvalBool evaluates the expression and requires a boolean result.
func (e *Expr) EvalBool(env Env) (bool, error) {
	v, err := e.Eval(env)
	if err != nil {
		return false, err
	}
	b, ok := v.(bool)
	if !ok {
		return false, fmt.Errorf("expr %q: expected boolean result, got %T", e.src, v)
	}
	return b, nil
}

// EvalNumber evaluates the expression and requires a numeric result.
func (e *Expr) EvalNumber(env Env) (float64, error) {
	v, err := e.Eval(env)
	if err != nil {
		return 0, err
	}
	f, ok := toNum(v)
	if !ok {
		return 0, fmt.Errorf("expr %q: expected numeric result, got %T", e.src, v)
	}
	return f, nil
}

// ---- AST ----

type node interface {
	eval(env Env) (Value, error)
}

type numberLit struct{ v float64 }
type stringLit struct{ v string }
type boolLit struct{ v bool }
type nullLit struct{}
type ident struct{ name string }
type unary struct {
	op      tokenKind
	operand node
}
type binary struct {
	op          tokenKind
	left, right node
}
type call struct {
	name string
	args []node
}

func (n *numberLit) eval(Env) (Value, error) { return n.v, nil }
func (n *stringLit) eval(Env) (Value, error) { return n.v, nil }
func (n *boolLit) eval(Env) (Value, error)   { return n.v, nil }
func (n *nullLit) eval(Env) (Value, error)   { return nil, nil }

func (n *ident) eval(env Env) (Value, error) {
	v, ok := env.Lookup(n.name)
	if !ok {
		return nil, fmt.Errorf("unknown identifier %q", n.name)
	}
	return v, nil
}

func (n *unary) eval(env Env) (Value, error) {
	v, err := n.operand.eval(env)
	if err != nil {
		return nil, err
	}
	switch n.op {
	case tMinus:
		f, ok := toNum(v)
		if !ok {
			return nil, fmt.Errorf("cannot negate non-number %T", v)
		}
		return -f, nil
	case tBang:
		b, ok := v.(bool)
		if !ok {
			return nil, fmt.Errorf("cannot apply ! to non-boolean %T", v)
		}
		return !b, nil
	}
	return nil, fmt.Errorf("invalid unary operator")
}

func (n *binary) eval(env Env) (Value, error) {
	// Short-circuit logical operators.
	if n.op == tAndAnd || n.op == tOrOr {
		l, err := n.left.eval(env)
		if err != nil {
			return nil, err
		}
		lb, ok := l.(bool)
		if !ok {
			return nil, fmt.Errorf("logical operator requires boolean operands, got %T", l)
		}
		if n.op == tAndAnd && !lb {
			return false, nil
		}
		if n.op == tOrOr && lb {
			return true, nil
		}
		r, err := n.right.eval(env)
		if err != nil {
			return nil, err
		}
		rb, ok := r.(bool)
		if !ok {
			return nil, fmt.Errorf("logical operator requires boolean operands, got %T", r)
		}
		return rb, nil
	}

	l, err := n.left.eval(env)
	if err != nil {
		return nil, err
	}
	r, err := n.right.eval(env)
	if err != nil {
		return nil, err
	}

	switch n.op {
	case tPlus, tMinus, tStar, tSlash, tPercent:
		lf, lok := toNum(l)
		rf, rok := toNum(r)
		if !lok || !rok {
			return nil, fmt.Errorf("arithmetic requires numbers, got %T and %T", l, r)
		}
		switch n.op {
		case tPlus:
			return lf + rf, nil
		case tMinus:
			return lf - rf, nil
		case tStar:
			return lf * rf, nil
		case tSlash:
			if rf == 0 {
				return nil, fmt.Errorf("division by zero")
			}
			return lf / rf, nil
		case tPercent:
			if rf == 0 {
				return nil, fmt.Errorf("modulo by zero")
			}
			return math.Mod(lf, rf), nil
		}
	case tLt, tLe, tGt, tGe:
		if lf, lok := toNum(l); lok {
			if rf, rok := toNum(r); rok {
				return compareNumbers(n.op, lf, rf), nil
			}
		}
		if ls, lok := l.(string); lok {
			if rs, rok := r.(string); rok {
				return compareStrings(n.op, ls, rs), nil
			}
		}
		return nil, fmt.Errorf("comparison requires two numbers or two strings, got %T and %T", l, r)
	case tEqEq, tBangEq:
		eq := valuesEqual(l, r)
		if n.op == tBangEq {
			return !eq, nil
		}
		return eq, nil
	}
	return nil, fmt.Errorf("invalid binary operator")
}

func (n *call) eval(env Env) (Value, error) {
	args := make([]float64, len(n.args))
	for i, a := range n.args {
		v, err := a.eval(env)
		if err != nil {
			return nil, err
		}
		f, ok := toNum(v)
		if !ok {
			return nil, fmt.Errorf("function %s: argument %d is not a number", n.name, i+1)
		}
		args[i] = f
	}
	switch n.name {
	case "min":
		if len(args) < 1 {
			return nil, fmt.Errorf("min: needs at least one argument")
		}
		m := args[0]
		for _, a := range args[1:] {
			m = math.Min(m, a)
		}
		return m, nil
	case "max":
		if len(args) < 1 {
			return nil, fmt.Errorf("max: needs at least one argument")
		}
		m := args[0]
		for _, a := range args[1:] {
			m = math.Max(m, a)
		}
		return m, nil
	case "abs":
		if len(args) != 1 {
			return nil, fmt.Errorf("abs: expects 1 argument")
		}
		return math.Abs(args[0]), nil
	case "round":
		if len(args) != 1 {
			return nil, fmt.Errorf("round: expects 1 argument")
		}
		return math.Round(args[0]), nil
	case "floor":
		if len(args) != 1 {
			return nil, fmt.Errorf("floor: expects 1 argument")
		}
		return math.Floor(args[0]), nil
	case "ceil":
		if len(args) != 1 {
			return nil, fmt.Errorf("ceil: expects 1 argument")
		}
		return math.Ceil(args[0]), nil
	}
	return nil, fmt.Errorf("unknown function %q", n.name)
}

func compareNumbers(op tokenKind, a, b float64) bool {
	switch op {
	case tLt:
		return a < b
	case tLe:
		return a <= b
	case tGt:
		return a > b
	case tGe:
		return a >= b
	}
	return false
}

func compareStrings(op tokenKind, a, b string) bool {
	switch op {
	case tLt:
		return a < b
	case tLe:
		return a <= b
	case tGt:
		return a > b
	case tGe:
		return a >= b
	}
	return false
}

func valuesEqual(a, b any) bool {
	if af, ok := toNum(a); ok {
		if bf, ok := toNum(b); ok {
			return af == bf
		}
		return false
	}
	return a == b
}

func toNum(v any) (float64, bool) {
	switch n := v.(type) {
	case float64:
		return n, true
	case int:
		return float64(n), true
	case int64:
		return float64(n), true
	case float32:
		return float64(n), true
	}
	return 0, false
}
