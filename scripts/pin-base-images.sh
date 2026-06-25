#!/usr/bin/env bash
# Resolve the box's CNB base images to immutable digests and print the lines to
# paste into builder.toml. Run at your desk (needs `crane` or `docker buildx`).
set -euo pipefail

resolve() {  # "image:tag" -> "image@sha256:..."
  if command -v crane >/dev/null 2>&1; then
    crane digest --full-ref "$1"
  elif command -v docker >/dev/null 2>&1; then
    local digest
    digest="$(docker buildx imagetools inspect "$1" --format '{{.Manifest.Digest}}')"
    echo "${1%%:*}@${digest}"
  else
    echo "need 'crane' or 'docker buildx' on PATH to resolve digests" >&2
    exit 1
  fi
}

build_img="paketobuildpacks/build-jammy-base:latest"
run_img="paketobuildpacks/run-jammy-base:latest"

echo "Resolving immutable digests…"
echo "  build-image = \"$(resolve "$build_img")\""
echo "  run-image   = \"$(resolve "$run_img")\""
echo
echo "Paste those into builder.toml [stack], then rebuild the box:"
echo "  pack builder create ard/box --config builder.toml"
