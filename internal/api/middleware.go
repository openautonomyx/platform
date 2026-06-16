package api

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"net/http"
	"time"
)

type ctxKey int

const (
	requestIDKey ctxKey = iota
	agentKey
)

// middleware decorates an http.Handler.
type middleware func(http.Handler) http.Handler

// chain applies middlewares so that the first listed is the outermost wrapper.
func chain(h http.Handler, mws ...middleware) http.Handler {
	for i := len(mws) - 1; i >= 0; i-- {
		h = mws[i](h)
	}
	return h
}

func requestIDFrom(ctx context.Context) string {
	if v, ok := ctx.Value(requestIDKey).(string); ok {
		return v
	}
	return ""
}

func newRequestID() string {
	var b [8]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "req-unknown"
	}
	return "req_" + hex.EncodeToString(b[:])
}

// requestIDMW assigns a request ID (honouring an inbound X-Request-Id) and
// echoes it on the response.
func requestIDMW(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id := r.Header.Get("X-Request-Id")
		if id == "" {
			id = newRequestID()
		}
		w.Header().Set("X-Request-Id", id)
		ctx := context.WithValue(r.Context(), requestIDKey, id)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// defaultAgent labels callers that do not identify themselves.
const defaultAgent = "anonymous"

// agentMW resolves the calling agent's identity from the request (the X-Agent
// header, falling back to X-Actor), stores it in the context, and echoes it on
// the response. Every decision, audit entry and access-log line is then
// attributable to an agent — the basis for governance in an agentic platform.
func agentMW(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		agent := r.Header.Get("X-Agent")
		if agent == "" {
			agent = r.Header.Get("X-Actor")
		}
		if agent == "" {
			agent = defaultAgent
		}
		w.Header().Set("X-Agent", agent)
		ctx := context.WithValue(r.Context(), agentKey, agent)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// agentFrom returns the calling agent's identity from the context.
func agentFrom(ctx context.Context) string {
	if v, ok := ctx.Value(agentKey).(string); ok && v != "" {
		return v
	}
	return defaultAgent
}

// statusRecorder captures the response status code for access logging.
type statusRecorder struct {
	http.ResponseWriter
	status int
	bytes  int
}

func (sr *statusRecorder) WriteHeader(code int) {
	sr.status = code
	sr.ResponseWriter.WriteHeader(code)
}

func (sr *statusRecorder) Write(b []byte) (int, error) {
	if sr.status == 0 {
		sr.status = http.StatusOK
	}
	n, err := sr.ResponseWriter.Write(b)
	sr.bytes += n
	return n, err
}

// logMW emits a structured access log line for every request.
func (s *Server) logMW(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		sr := &statusRecorder{ResponseWriter: w, status: 0}
		next.ServeHTTP(sr, r)
		if r.URL.Path == "/healthz" || r.URL.Path == "/readyz" {
			return // avoid log spam from k8s probes
		}
		s.log.Info("request",
			"method", r.Method,
			"path", r.URL.Path,
			"status", sr.status,
			"bytes", sr.bytes,
			"durationMs", time.Since(start).Milliseconds(),
			"requestId", requestIDFrom(r.Context()),
			"agent", agentFrom(r.Context()),
			"remote", r.RemoteAddr,
		)
	})
}

// recoverMW converts panics into 500 responses so a single bad request can
// never take down the server.
func (s *Server) recoverMW(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if rec := recover(); rec != nil {
				s.log.Error("panic recovered",
					"error", rec,
					"path", r.URL.Path,
					"requestId", requestIDFrom(r.Context()),
				)
				writeError(w, r, http.StatusInternalServerError, "internal server error")
			}
		}()
		next.ServeHTTP(w, r)
	})
}
