// Package catalog is a concurrency-safe registry of decision models. Each model
// is compiled on registration so evaluation never pays a parsing cost and bad
// models are rejected up front. It also tracks per-model version history.
package catalog

import (
	"sort"
	"sync"
	"time"

	"github.com/openautonomyx/platform/internal/engine"
)

// VersionRef is one entry in a model's version history.
type VersionRef struct {
	Version   string    `json:"version"`
	CreatedAt time.Time `json:"createdAt"`
}

// Catalog stores decision models and their compiled forms.
type Catalog struct {
	mu       sync.RWMutex
	models   map[string]*engine.Model
	compiled map[string]*engine.Compiled
	versions map[string][]VersionRef
}

// New returns an empty catalog.
func New() *Catalog {
	return &Catalog{
		models:   map[string]*engine.Model{},
		compiled: map[string]*engine.Compiled{},
		versions: map[string][]VersionRef{},
	}
}

// Put validates, compiles and stores a model, returning the compiled form. A
// model with an existing ID replaces it and appends to its version history.
func (c *Catalog) Put(m *engine.Model) (*engine.Compiled, error) {
	compiled, err := engine.Compile(m)
	if err != nil {
		return nil, err
	}
	if m.CreatedAt.IsZero() {
		m.CreatedAt = time.Now().UTC()
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	c.models[m.ID] = m
	c.compiled[m.ID] = compiled
	hist := c.versions[m.ID]
	if len(hist) == 0 || hist[len(hist)-1].Version != m.Version {
		c.versions[m.ID] = append(hist, VersionRef{Version: m.Version, CreatedAt: m.CreatedAt})
	}
	return compiled, nil
}

// Get returns the model with the given id.
func (c *Catalog) Get(id string) (*engine.Model, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	m, ok := c.models[id]
	return m, ok
}

// Compiled returns the compiled form of the model with the given id.
func (c *Catalog) Compiled(id string) (*engine.Compiled, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	cm, ok := c.compiled[id]
	return cm, ok
}

// List returns all models sorted by name.
func (c *Catalog) List() []*engine.Model {
	c.mu.RLock()
	defer c.mu.RUnlock()
	out := make([]*engine.Model, 0, len(c.models))
	for _, m := range c.models {
		out = append(out, m)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out
}

// Versions returns the version history for a model.
func (c *Catalog) Versions(id string) []VersionRef {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return append([]VersionRef(nil), c.versions[id]...)
}

// Len returns the number of registered models.
func (c *Catalog) Len() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return len(c.models)
}
