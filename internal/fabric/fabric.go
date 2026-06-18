// Package fabric is MetaKube's data fabric: a pluggable framework for ingesting
// external signals into decisions. Connectors (e.g. Facebook Graph) register
// with the fabric and advertise their configuration and authorization status.
// The fabric itself is dependency-free; individual connectors may make outbound
// calls only when explicitly configured.
package fabric

import (
	"sync"
	"time"
)

// Signal is a unit of external data ingested for use in a decision.
type Signal struct {
	Connector string         `json:"connector"`
	Kind      string         `json:"kind"`
	Value     any            `json:"value"`
	Meta      map[string]any `json:"meta,omitempty"`
	FetchedAt time.Time      `json:"fetchedAt"`
}

// Status describes a connector's identity and readiness.
type Status struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	Description string   `json:"description"`
	AuthType    string   `json:"authType"`
	Configured  bool     `json:"configured"`
	Scopes      []string `json:"scopes,omitempty"`
}

// Connector is an external data source plugged into the fabric.
type Connector interface {
	Status() Status
}

// Fabric is the connector registry — the "fabricator" that assembles the data
// fabric from individual connectors. It is safe for concurrent use.
type Fabric struct {
	mu         sync.RWMutex
	connectors map[string]Connector
	order      []string
}

// New returns an empty fabric.
func New() *Fabric { return &Fabric{connectors: map[string]Connector{}} }

// Register adds (or replaces) a connector, keyed by its status ID.
func (f *Fabric) Register(c Connector) {
	f.mu.Lock()
	defer f.mu.Unlock()
	id := c.Status().ID
	if _, ok := f.connectors[id]; !ok {
		f.order = append(f.order, id)
	}
	f.connectors[id] = c
}

// Get returns a connector by ID.
func (f *Fabric) Get(id string) (Connector, bool) {
	f.mu.RLock()
	defer f.mu.RUnlock()
	c, ok := f.connectors[id]
	return c, ok
}

// List returns all connectors in registration order.
func (f *Fabric) List() []Connector {
	f.mu.RLock()
	defer f.mu.RUnlock()
	out := make([]Connector, 0, len(f.order))
	for _, id := range f.order {
		out = append(out, f.connectors[id])
	}
	return out
}
