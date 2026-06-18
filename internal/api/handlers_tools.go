package api

import (
	"net/http"

	"github.com/openautonomyx/platform/internal/engine"
)

// jsonSchemaProperty is one property in a JSON Schema object.
type jsonSchemaProperty struct {
	Type        string   `json:"type"`
	Description string   `json:"description,omitempty"`
	Enum        []string `json:"enum,omitempty"`
	Minimum     *float64 `json:"minimum,omitempty"`
	Maximum     *float64 `json:"maximum,omitempty"`
}

// jsonSchema is a minimal JSON Schema object describing a tool's parameters.
type jsonSchema struct {
	Type                 string                        `json:"type"`
	Properties           map[string]jsonSchemaProperty `json:"properties"`
	Required             []string                      `json:"required,omitempty"`
	AdditionalProperties bool                          `json:"additionalProperties"`
}

// toolInvoke documents how an agent calls the tool.
type toolInvoke struct {
	Method         string `json:"method"`
	Endpoint       string `json:"endpoint"`
	ArgumentsField string `json:"argumentsField"`
}

// toolSpec is a function-calling tool definition (Anthropic/OpenAI style) that
// an AI agent can use directly. Each decision service is exposed as one tool.
type toolSpec struct {
	Name        string     `json:"name"`
	Description string     `json:"description"`
	InputSchema jsonSchema `json:"input_schema"`
	Invoke      toolInvoke `json:"invoke"`
}

// handleListTools exposes every decision service as an agent-callable tool so
// AI agents can discover and invoke decisions via function calling.
func (s *Server) handleListTools(w http.ResponseWriter, r *http.Request) {
	models := s.cat.List()
	tools := make([]toolSpec, 0, len(models))
	for _, m := range models {
		tools = append(tools, modelToTool(m))
	}
	writeJSON(w, http.StatusOK, map[string]any{"count": len(tools), "tools": tools})
}

func modelToTool(m *engine.Model) toolSpec {
	props := make(map[string]jsonSchemaProperty, len(m.Inputs))
	var required []string
	for _, in := range m.Inputs {
		p := jsonSchemaProperty{
			Type:        schemaType(in.Type),
			Description: firstNonEmpty(in.Label, in.Key),
			Enum:        in.Enum,
			Minimum:     in.Min,
			Maximum:     in.Max,
		}
		props[in.Key] = p
		if in.Required {
			required = append(required, in.Key)
		}
	}
	return toolSpec{
		Name:        m.ID,
		Description: firstNonEmpty(m.Description, m.Name),
		InputSchema: jsonSchema{
			Type:                 "object",
			Properties:           props,
			Required:             required,
			AdditionalProperties: false,
		},
		Invoke: toolInvoke{
			Method:         http.MethodPost,
			Endpoint:       "/v1/models/" + m.ID + "/execute",
			ArgumentsField: "inputs",
		},
	}
}

func schemaType(t string) string {
	switch t {
	case "number":
		return "number"
	case "boolean":
		return "boolean"
	default:
		return "string"
	}
}

func firstNonEmpty(vals ...string) string {
	for _, v := range vals {
		if v != "" {
			return v
		}
	}
	return ""
}
