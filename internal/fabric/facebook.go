package fabric

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const fbGraphVersion = "v19.0"

// FacebookConfig holds the credentials and OAuth settings for the Facebook
// Graph connector. All fields come from configuration/environment; nothing is
// hardcoded.
type FacebookConfig struct {
	AppID       string
	AppSecret   string
	RedirectURI string
	AccessToken string
	Scopes      []string // fine-grained permissions to request during OAuth
}

// Facebook is a data-fabric connector for the Facebook Graph API.
type Facebook struct {
	cfg  FacebookConfig
	http *http.Client
}

// NewFacebook builds a Facebook connector.
func NewFacebook(cfg FacebookConfig) *Facebook {
	return &Facebook{cfg: cfg, http: &http.Client{Timeout: 10 * time.Second}}
}

// Status implements Connector.
func (f *Facebook) Status() Status {
	return Status{
		ID:          "facebook",
		Name:        "Facebook Graph",
		Description: "Ingests Facebook Graph data (e.g. comments) via OAuth with fine-grained, user-authorized scopes.",
		AuthType:    "oauth2",
		Configured:  f.Configured(),
		Scopes:      f.cfg.Scopes,
	}
}

// Configured reports whether a live Graph API call can be attempted (an access
// token is present).
func (f *Facebook) Configured() bool {
	return f.cfg.AppID != "" && f.cfg.AccessToken != ""
}

// AuthorizationURL builds the OAuth consent URL used to obtain the user's
// authorization with the configured fine-grained scopes. It is a pure function
// (no network) and never exposes the app secret.
func (f *Facebook) AuthorizationURL(state string) (string, error) {
	if f.cfg.AppID == "" || f.cfg.RedirectURI == "" {
		return "", fmt.Errorf("facebook: FACEBOOK_APP_ID and FACEBOOK_REDIRECT_URI must be configured")
	}
	q := url.Values{}
	q.Set("client_id", f.cfg.AppID)
	q.Set("redirect_uri", f.cfg.RedirectURI)
	q.Set("response_type", "code")
	q.Set("state", state)
	if len(f.cfg.Scopes) > 0 {
		q.Set("scope", strings.Join(f.cfg.Scopes, ","))
	}
	return "https://www.facebook.com/" + fbGraphVersion + "/dialog/oauth?" + q.Encode(), nil
}

// Comment is a Facebook comment.
type Comment struct {
	ID        string `json:"id"`
	Message   string `json:"message"`
	From      string `json:"from,omitempty"`
	CreatedAt string `json:"createdAt,omitempty"`
}

// FetchComments fetches comments for a Graph object id. It requires a configured
// access token and outbound access to graph.facebook.com.
//
// NOTE: this live call is not exercised in CI (no credentials or egress in the
// build environment); the request shaping follows the documented Graph API.
func (f *Facebook) FetchComments(ctx context.Context, objectID string) ([]Comment, error) {
	if !f.Configured() {
		return nil, fmt.Errorf("facebook connector not configured: set FACEBOOK_APP_ID and FACEBOOK_ACCESS_TOKEN")
	}
	if strings.TrimSpace(objectID) == "" {
		return nil, fmt.Errorf("objectId is required")
	}
	endpoint := fmt.Sprintf("https://graph.facebook.com/%s/%s/comments", fbGraphVersion, url.PathEscape(objectID))
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return nil, err
	}
	q := req.URL.Query()
	q.Set("access_token", f.cfg.AccessToken)
	req.URL.RawQuery = q.Encode()

	resp, err := f.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("facebook graph request failed: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("facebook graph returned status %s", resp.Status)
	}
	var body struct {
		Data []struct {
			ID          string `json:"id"`
			Message     string `json:"message"`
			CreatedTime string `json:"created_time"`
			From        struct {
				Name string `json:"name"`
			} `json:"from"`
		} `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		return nil, fmt.Errorf("decoding graph response: %w", err)
	}
	out := make([]Comment, 0, len(body.Data))
	for _, d := range body.Data {
		out = append(out, Comment{ID: d.ID, Message: d.Message, From: d.From.Name, CreatedAt: d.CreatedTime})
	}
	return out, nil
}

// FacebookConfigFromEnv reads connector configuration from the environment via
// the supplied getenv function:
//
//	FACEBOOK_APP_ID, FACEBOOK_APP_SECRET, FACEBOOK_REDIRECT_URI,
//	FACEBOOK_ACCESS_TOKEN, FACEBOOK_SCOPES (comma-separated)
func FacebookConfigFromEnv(getenv func(string) string) FacebookConfig {
	var scopes []string
	if s := getenv("FACEBOOK_SCOPES"); s != "" {
		for _, p := range strings.Split(s, ",") {
			if p = strings.TrimSpace(p); p != "" {
				scopes = append(scopes, p)
			}
		}
	}
	return FacebookConfig{
		AppID:       getenv("FACEBOOK_APP_ID"),
		AppSecret:   getenv("FACEBOOK_APP_SECRET"),
		RedirectURI: getenv("FACEBOOK_REDIRECT_URI"),
		AccessToken: getenv("FACEBOOK_ACCESS_TOKEN"),
		Scopes:      scopes,
	}
}
