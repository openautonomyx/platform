package expr

import (
	"fmt"
	"strconv"
	"strings"
)

func parseFloat(s string) (float64, error) { return strconv.ParseFloat(s, 64) }

type tokenKind int

const (
	tEOF tokenKind = iota
	tNumber
	tString
	tIdent
	tTrue
	tFalse
	tNull
	tLParen
	tRParen
	tComma
	tPlus
	tMinus
	tStar
	tSlash
	tPercent
	tBang
	tLt
	tLe
	tGt
	tGe
	tEqEq
	tBangEq
	tAndAnd
	tOrOr
)

type token struct {
	kind tokenKind
	text string
}

func isIdentStart(c rune) bool {
	return c == '_' || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')
}

func isIdentPart(c rune) bool {
	return isIdentStart(c) || (c >= '0' && c <= '9') || c == '.'
}

func isDigit(c rune) bool { return c >= '0' && c <= '9' }

func lex(src string) ([]token, error) {
	var toks []token
	rs := []rune(src)
	i := 0
	for i < len(rs) {
		c := rs[i]
		switch {
		case c == ' ' || c == '\t' || c == '\n' || c == '\r':
			i++
		case isDigit(c) || (c == '.' && i+1 < len(rs) && isDigit(rs[i+1])):
			j := i
			seenDot := false
			for j < len(rs) && (isDigit(rs[j]) || (rs[j] == '.' && !seenDot)) {
				if rs[j] == '.' {
					seenDot = true
				}
				j++
			}
			toks = append(toks, token{tNumber, string(rs[i:j])})
			i = j
		case c == '\'' || c == '"':
			quote := c
			j := i + 1
			var sb strings.Builder
			for j < len(rs) && rs[j] != quote {
				if rs[j] == '\\' && j+1 < len(rs) {
					sb.WriteRune(rs[j+1])
					j += 2
					continue
				}
				sb.WriteRune(rs[j])
				j++
			}
			if j >= len(rs) {
				return nil, fmt.Errorf("unterminated string literal")
			}
			toks = append(toks, token{tString, sb.String()})
			i = j + 1
		case isIdentStart(c):
			j := i
			for j < len(rs) && isIdentPart(rs[j]) {
				j++
			}
			word := string(rs[i:j])
			i = j
			switch word {
			case "true":
				toks = append(toks, token{tTrue, word})
			case "false":
				toks = append(toks, token{tFalse, word})
			case "null":
				toks = append(toks, token{tNull, word})
			default:
				toks = append(toks, token{tIdent, word})
			}
		default:
			if i+1 < len(rs) {
				switch string(rs[i : i+2]) {
				case "&&":
					toks = append(toks, token{tAndAnd, "&&"})
					i += 2
					continue
				case "||":
					toks = append(toks, token{tOrOr, "||"})
					i += 2
					continue
				case "==":
					toks = append(toks, token{tEqEq, "=="})
					i += 2
					continue
				case "!=":
					toks = append(toks, token{tBangEq, "!="})
					i += 2
					continue
				case "<=":
					toks = append(toks, token{tLe, "<="})
					i += 2
					continue
				case ">=":
					toks = append(toks, token{tGe, ">="})
					i += 2
					continue
				}
			}
			switch c {
			case '(':
				toks = append(toks, token{tLParen, "("})
			case ')':
				toks = append(toks, token{tRParen, ")"})
			case ',':
				toks = append(toks, token{tComma, ","})
			case '+':
				toks = append(toks, token{tPlus, "+"})
			case '-':
				toks = append(toks, token{tMinus, "-"})
			case '*':
				toks = append(toks, token{tStar, "*"})
			case '/':
				toks = append(toks, token{tSlash, "/"})
			case '%':
				toks = append(toks, token{tPercent, "%"})
			case '!':
				toks = append(toks, token{tBang, "!"})
			case '<':
				toks = append(toks, token{tLt, "<"})
			case '>':
				toks = append(toks, token{tGt, ">"})
			default:
				return nil, fmt.Errorf("unexpected character %q", string(c))
			}
			i++
		}
	}
	toks = append(toks, token{tEOF, ""})
	return toks, nil
}

// ---- parser (precedence climbing) ----

var binPrec = map[tokenKind]int{
	tOrOr:    1,
	tAndAnd:  2,
	tEqEq:    3,
	tBangEq:  3,
	tLt:      4,
	tLe:      4,
	tGt:      4,
	tGe:      4,
	tPlus:    5,
	tMinus:   5,
	tStar:    6,
	tSlash:   6,
	tPercent: 6,
}

type parser struct {
	toks []token
	pos  int
}

func (p *parser) peek() token { return p.toks[p.pos] }
func (p *parser) next() token {
	t := p.toks[p.pos]
	p.pos++
	return t
}

func (p *parser) parseExpr(minPrec int) (node, error) {
	left, err := p.parseUnary()
	if err != nil {
		return nil, err
	}
	for {
		op := p.peek().kind
		prec, ok := binPrec[op]
		if !ok || prec < minPrec {
			break
		}
		p.next()
		right, err := p.parseExpr(prec + 1)
		if err != nil {
			return nil, err
		}
		left = &binary{op: op, left: left, right: right}
	}
	return left, nil
}

func (p *parser) parseUnary() (node, error) {
	t := p.peek()
	if t.kind == tMinus || t.kind == tBang {
		p.next()
		operand, err := p.parseUnary()
		if err != nil {
			return nil, err
		}
		return &unary{op: t.kind, operand: operand}, nil
	}
	return p.parsePrimary()
}

func (p *parser) parsePrimary() (node, error) {
	t := p.next()
	switch t.kind {
	case tNumber:
		f, err := parseFloat(t.text)
		if err != nil {
			return nil, fmt.Errorf("invalid number %q", t.text)
		}
		return &numberLit{f}, nil
	case tString:
		return &stringLit{t.text}, nil
	case tTrue:
		return &boolLit{true}, nil
	case tFalse:
		return &boolLit{false}, nil
	case tNull:
		return &nullLit{}, nil
	case tIdent:
		if p.peek().kind == tLParen {
			p.next() // consume '('
			var args []node
			if p.peek().kind != tRParen {
				for {
					a, err := p.parseExpr(0)
					if err != nil {
						return nil, err
					}
					args = append(args, a)
					if p.peek().kind == tComma {
						p.next()
						continue
					}
					break
				}
			}
			if p.peek().kind != tRParen {
				return nil, fmt.Errorf("expected ')' after function arguments")
			}
			p.next()
			return &call{name: t.text, args: args}, nil
		}
		return &ident{t.text}, nil
	case tLParen:
		inner, err := p.parseExpr(0)
		if err != nil {
			return nil, err
		}
		if p.peek().kind != tRParen {
			return nil, fmt.Errorf("expected ')'")
		}
		p.next()
		return inner, nil
	default:
		return nil, fmt.Errorf("unexpected token %q", t.text)
	}
}
