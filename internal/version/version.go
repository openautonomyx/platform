// Package version exposes build metadata. The variables are intended to be set
// at build time via -ldflags, e.g.
//
//	go build -ldflags "-X github.com/openautonomyx/platform/internal/version.Version=1.2.3"
package version

import "runtime"

var (
	// Version is the semantic version of the build.
	Version = "0.1.0"
	// Commit is the git commit the binary was built from.
	Commit = "dev"
	// BuildDate is the RFC3339 build timestamp.
	BuildDate = "unknown"
)

// Info is a snapshot of build metadata.
type Info struct {
	Service   string `json:"service"`
	Version   string `json:"version"`
	Commit    string `json:"commit"`
	BuildDate string `json:"buildDate"`
	GoVersion string `json:"goVersion"`
}

// Get returns the current build info.
func Get() Info {
	return Info{
		Service:   "metakube",
		Version:   Version,
		Commit:    Commit,
		BuildDate: BuildDate,
		GoVersion: runtime.Version(),
	}
}
