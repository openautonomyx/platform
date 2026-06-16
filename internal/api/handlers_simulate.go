package api

import (
	"math"
	"math/rand/v2"
	"net/http"

	"github.com/openautonomyx/platform/internal/engine"
	"github.com/openautonomyx/platform/internal/store"
)

const maxSimulate = 2000

type simulateRequest struct {
	Count int     `json:"count"`
	Seed  *uint64 `json:"seed,omitempty"`
}

// handleSimulate generates synthetic, schema-valid inputs, executes the model
// for each, and records the runs. It is the fastest way to populate monitoring
// dashboards and exercise the review queue (Decision Execution at scale).
func (s *Server) handleSimulate(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	compiled, ok := s.cat.Compiled(id)
	if !ok {
		writeError(w, r, http.StatusNotFound, "model not found")
		return
	}
	model, _ := s.cat.Get(id)

	var req simulateRequest
	if err := decodeOptionalJSON(w, r, &req); err != nil {
		writeError(w, r, http.StatusBadRequest, err.Error())
		return
	}
	if req.Count <= 0 {
		req.Count = 100
	}
	if req.Count > maxSimulate {
		req.Count = maxSimulate
	}

	var rng *rand.Rand
	if req.Seed != nil {
		rng = rand.New(rand.NewPCG(*req.Seed, 0x9e3779b97f4a7c15))
	} else {
		rng = rand.New(rand.NewPCG(rand.Uint64(), rand.Uint64()))
	}

	byDecision := map[string]int{}
	executed, errCount := 0, 0
	for i := 0; i < req.Count; i++ {
		inputs := sampleInputs(model, rng)
		result, err := compiled.Evaluate(inputs)
		if err != nil {
			errCount++
			continue
		}
		applied := s.store.ApplyGovernance(id, inputs, &result.Outcome)
		status := store.StatusFinal
		if result.Outcome.Decision == string(engine.Review) {
			status = store.StatusPendingReview
		}
		s.store.AddRun(&store.Run{
			ModelID: id, ModelVersion: model.Version, Inputs: inputs,
			Outcome: result.Outcome, Status: status, Source: "simulation", Policies: applied,
		})
		byDecision[result.Outcome.Decision]++
		executed++
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"modelId":    id,
		"requested":  req.Count,
		"executed":   executed,
		"errors":     errCount,
		"byDecision": byDecision,
	})
}

// sampleInputs draws a random, schema-valid input set for a model.
func sampleInputs(m *engine.Model, rng *rand.Rand) map[string]any {
	in := make(map[string]any, len(m.Inputs))
	for _, f := range m.Inputs {
		switch f.Type {
		case "number":
			in[f.Key] = sampleNumber(f, rng)
		case "string":
			if len(f.Enum) > 0 {
				in[f.Key] = f.Enum[rng.IntN(len(f.Enum))]
			} else {
				in[f.Key] = "sample"
			}
		case "boolean":
			in[f.Key] = rng.IntN(2) == 0
		}
	}
	return in
}

func sampleNumber(f engine.InputField, rng *rand.Rand) float64 {
	lo, hi := 0.0, 100.0
	switch {
	case f.Min != nil && f.Max != nil:
		lo, hi = *f.Min, *f.Max
	case f.Example != nil:
		ex := toFloatAny(f.Example)
		if f.Min != nil {
			lo = *f.Min
		}
		hi = ex * 2.2
		if hi <= lo {
			hi = lo + 1
		}
	case f.Min != nil:
		lo = *f.Min
		hi = lo + 100
	}
	if hi <= lo {
		hi = lo + 1
	}
	return math.Round(lo + rng.Float64()*(hi-lo))
}

func toFloatAny(v any) float64 {
	switch n := v.(type) {
	case float64:
		return n
	case float32:
		return float64(n)
	case int:
		return float64(n)
	case int64:
		return float64(n)
	}
	return 0
}
