// Command metakube runs the MetaKube Decision Intelligence Platform service:
// a Kubernetes-native HTTP API for modeling, executing, monitoring and
// governing decisions.
package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"

	"github.com/openautonomyx/platform/internal/api"
	"github.com/openautonomyx/platform/internal/catalog"
	"github.com/openautonomyx/platform/internal/fabric"
	"github.com/openautonomyx/platform/internal/store"
	"github.com/openautonomyx/platform/internal/version"
)

func main() {
	logger := newLogger()
	cfg := api.ConfigFromEnv()

	cat := catalog.New()
	catalog.Seed(cat)
	st := store.New()

	// Seed a bootstrap author identity so RBAC enforce mode is usable out of
	// the box (registering agents otherwise requires the author role).
	rootAgent := os.Getenv("METAKUBE_ROOT_AGENT")
	if rootAgent == "" {
		rootAgent = "root"
	}
	if _, err := st.RegisterAgent(store.Agent{
		ID: rootAgent, Name: "Root Operator", Description: "Bootstrap author identity", Roles: []string{"*"},
	}, "system"); err != nil {
		logger.Error("failed to seed root agent", "error", err)
	}

	// Data fabric: register external-signal connectors. Connectors are inert
	// until their credentials are supplied via the environment.
	fab := fabric.New()
	fab.Register(fabric.NewFacebook(fabric.FacebookConfigFromEnv(os.Getenv)))

	srv := api.NewServer(cfg, cat, st, fab, logger)

	httpServer := &http.Server{
		Addr:              cfg.Addr,
		Handler:           srv.Handler(),
		ReadTimeout:       cfg.ReadTimeout,
		ReadHeaderTimeout: cfg.ReadTimeout,
		WriteTimeout:      cfg.WriteTimeout,
		IdleTimeout:       cfg.IdleTimeout,
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	go func() {
		info := version.Get()
		logger.Info("metakube starting",
			"addr", cfg.Addr, "version", info.Version, "commit", info.Commit, "models", cat.Len())
		if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("server error", "error", err)
			stop()
		}
	}()

	<-ctx.Done()
	logger.Info("shutdown signal received, draining connections")
	srv.SetReady(false)

	shutdownCtx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
	defer cancel()
	if err := httpServer.Shutdown(shutdownCtx); err != nil {
		logger.Error("graceful shutdown failed", "error", err)
		_ = httpServer.Close()
		os.Exit(1)
	}
	logger.Info("shutdown complete")
}

func newLogger() *slog.Logger {
	level := slog.LevelInfo
	switch strings.ToLower(os.Getenv("LOG_LEVEL")) {
	case "debug":
		level = slog.LevelDebug
	case "warn":
		level = slog.LevelWarn
	case "error":
		level = slog.LevelError
	}
	h := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: level})
	return slog.New(h).With("service", "metakube")
}
