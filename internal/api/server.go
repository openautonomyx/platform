package api

import (
	"log/slog"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	"github.com/openautonomyx/platform/internal/catalog"
	"github.com/openautonomyx/platform/internal/store"
)

// Config holds tunable server settings, populated from the environment.
type Config struct {
	Addr            string
	ReadTimeout     time.Duration
	WriteTimeout    time.Duration
	IdleTimeout     time.Duration
	ShutdownTimeout time.Duration
	// AccessMode is "open" (no enforcement, default) or "enforce" (RBAC).
	AccessMode string
}

// DefaultConfig returns sensible production defaults.
func DefaultConfig() Config {
	return Config{
		Addr:            ":8080",
		ReadTimeout:     10 * time.Second,
		WriteTimeout:    30 * time.Second,
		IdleTimeout:     120 * time.Second,
		ShutdownTimeout: 15 * time.Second,
		AccessMode:      accessOpen,
	}
}

// ConfigFromEnv layers environment overrides on top of DefaultConfig.
//
//	PORT                 -> Addr (":"+PORT)
//	METAKUBE_ADDR        -> Addr (takes precedence over PORT)
//	READ_TIMEOUT_SECONDS, WRITE_TIMEOUT_SECONDS, IDLE_TIMEOUT_SECONDS,
//	SHUTDOWN_TIMEOUT_SECONDS
//	METAKUBE_ACCESS      -> AccessMode ("open" | "enforce")
func ConfigFromEnv() Config {
	c := DefaultConfig()
	if p := os.Getenv("PORT"); p != "" {
		c.Addr = ":" + p
	}
	if a := os.Getenv("METAKUBE_ADDR"); a != "" {
		c.Addr = a
	}
	c.ReadTimeout = envDuration("READ_TIMEOUT_SECONDS", c.ReadTimeout)
	c.WriteTimeout = envDuration("WRITE_TIMEOUT_SECONDS", c.WriteTimeout)
	c.IdleTimeout = envDuration("IDLE_TIMEOUT_SECONDS", c.IdleTimeout)
	c.ShutdownTimeout = envDuration("SHUTDOWN_TIMEOUT_SECONDS", c.ShutdownTimeout)
	if m := os.Getenv("METAKUBE_ACCESS"); m != "" {
		c.AccessMode = strings.ToLower(m)
	}
	return c
}

func envDuration(key string, def time.Duration) time.Duration {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n >= 0 {
			return time.Duration(n) * time.Second
		}
	}
	return def
}

// Server wires the decision catalog and operational store to HTTP handlers.
type Server struct {
	cfg     Config
	cat     *catalog.Catalog
	store   *store.Store
	log     *slog.Logger
	handler http.Handler
	started time.Time
	ready   atomic.Bool
}

// NewServer constructs a ready-to-serve Server.
func NewServer(cfg Config, cat *catalog.Catalog, st *store.Store, logger *slog.Logger) *Server {
	if logger == nil {
		logger = slog.New(slog.NewJSONHandler(os.Stdout, nil))
	}
	s := &Server{
		cfg:     cfg,
		cat:     cat,
		store:   st,
		log:     logger,
		started: time.Now(),
	}
	s.ready.Store(true)
	s.handler = s.routes()
	return s
}

// Handler returns the fully decorated HTTP handler.
func (s *Server) Handler() http.Handler { return s.handler }

// Config returns the server configuration.
func (s *Server) Config() Config { return s.cfg }

// SetReady toggles readiness, which the /readyz probe reflects.
func (s *Server) SetReady(ready bool) { s.ready.Store(ready) }

func (s *Server) routes() http.Handler {
	mux := http.NewServeMux()

	// Operational endpoints.
	mux.HandleFunc("GET /healthz", s.handleHealthz)
	mux.HandleFunc("GET /readyz", s.handleReadyz)
	mux.HandleFunc("GET /version", s.handleVersion)
	mux.HandleFunc("GET /metrics", s.handlePrometheus)
	mux.HandleFunc("GET /", s.handleRoot)

	// Decision modeling & service composition.
	mux.HandleFunc("GET /v1/models", s.handleListModels)
	mux.HandleFunc("POST /v1/models", s.handleCreateModel)
	mux.HandleFunc("POST /v1/models/validate", s.handleValidateModel)
	mux.HandleFunc("GET /v1/models/{id}", s.handleGetModel)
	mux.HandleFunc("DELETE /v1/models/{id}", s.handleDeleteModel)
	mux.HandleFunc("GET /v1/models/{id}/versions", s.handleModelVersions)
	mux.HandleFunc("GET /v1/services", s.handleListServices)

	// Decision execution.
	mux.HandleFunc("POST /v1/models/{id}/execute", s.handleExecute)
	mux.HandleFunc("POST /v1/models/{id}/simulate", s.handleSimulate)

	// Decision monitoring.
	mux.HandleFunc("GET /v1/runs", s.handleListRuns)
	mux.HandleFunc("GET /v1/runs/{id}", s.handleGetRun)
	mux.HandleFunc("GET /v1/metrics", s.handleMetrics)

	// Decision collaboration (human-in-the-loop).
	mux.HandleFunc("GET /v1/reviews", s.handleListReviews)
	mux.HandleFunc("POST /v1/reviews/{id}/resolve", s.handleResolveReview)

	// Decision governance.
	mux.HandleFunc("GET /v1/audit", s.handleListAudit)
	mux.HandleFunc("GET /v1/policies", s.handleListPolicies)
	mux.HandleFunc("PUT /v1/policies/{id}", s.handleUpdatePolicy)

	// Durable, platform-native agent identities.
	mux.HandleFunc("GET /v1/agents", s.handleListAgents)
	mux.HandleFunc("POST /v1/agents", s.handleRegisterAgent)
	mux.HandleFunc("GET /v1/agents/{id}", s.handleGetAgent)

	// Decision services as agent-callable tools (function-calling specs).
	mux.HandleFunc("GET /v1/tools", s.handleListTools)

	return chain(mux, requestIDMW, s.agentMW, s.logMW, s.recoverMW, s.authMW)
}
