package fabric

import (
	"context"
	"net/url"
	"testing"
)

func TestFabricRegistry(t *testing.T) {
	f := New()
	f.Register(NewFacebook(FacebookConfig{}))
	if len(f.List()) != 1 {
		t.Fatalf("expected 1 connector, got %d", len(f.List()))
	}
	if _, ok := f.Get("facebook"); !ok {
		t.Error("facebook connector should be registered")
	}
	if _, ok := f.Get("nope"); ok {
		t.Error("unexpected connector found")
	}
}

func TestFacebookConfiguredGating(t *testing.T) {
	if NewFacebook(FacebookConfig{AppID: "a"}).Configured() {
		t.Error("connector without token must not be configured")
	}
	if !NewFacebook(FacebookConfig{AppID: "a", AccessToken: "t"}).Configured() {
		t.Error("connector with app id + token should be configured")
	}
	// An unconfigured connector must refuse live calls rather than dial out.
	_, err := NewFacebook(FacebookConfig{}).FetchComments(context.Background(), "123")
	if err == nil {
		t.Error("expected error fetching from an unconfigured connector")
	}
}

func TestFacebookAuthorizationURL(t *testing.T) {
	fb := NewFacebook(FacebookConfig{
		AppID:       "app123",
		RedirectURI: "https://example.com/cb",
		Scopes:      []string{"public_profile", "pages_read_engagement"},
	})
	raw, err := fb.AuthorizationURL("xyz")
	if err != nil {
		t.Fatalf("AuthorizationURL error: %v", err)
	}
	u, err := url.Parse(raw)
	if err != nil {
		t.Fatalf("returned URL did not parse: %v", err)
	}
	q := u.Query()
	if q.Get("client_id") != "app123" {
		t.Errorf("client_id = %q", q.Get("client_id"))
	}
	if q.Get("redirect_uri") != "https://example.com/cb" {
		t.Errorf("redirect_uri = %q", q.Get("redirect_uri"))
	}
	if q.Get("state") != "xyz" {
		t.Errorf("state = %q", q.Get("state"))
	}
	if q.Get("scope") != "public_profile,pages_read_engagement" {
		t.Errorf("scope = %q", q.Get("scope"))
	}
	if q.Get("response_type") != "code" {
		t.Errorf("response_type = %q", q.Get("response_type"))
	}

	// Missing redirect URI is an error.
	if _, err := NewFacebook(FacebookConfig{AppID: "a"}).AuthorizationURL("s"); err == nil {
		t.Error("expected error when redirect URI is missing")
	}
}

func TestFacebookConfigFromEnv(t *testing.T) {
	env := map[string]string{
		"FACEBOOK_APP_ID":       "id",
		"FACEBOOK_SCOPES":       "a, b ,c",
		"FACEBOOK_ACCESS_TOKEN": "tok",
	}
	cfg := FacebookConfigFromEnv(func(k string) string { return env[k] })
	if cfg.AppID != "id" || cfg.AccessToken != "tok" {
		t.Errorf("unexpected config: %+v", cfg)
	}
	if len(cfg.Scopes) != 3 || cfg.Scopes[0] != "a" || cfg.Scopes[2] != "c" {
		t.Errorf("scopes not parsed/trimmed: %v", cfg.Scopes)
	}
}
