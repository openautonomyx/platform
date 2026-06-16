# MetaKube — build & deploy automation
#
# Common targets:
#   make run            run the service locally on :8080
#   make test           run unit tests
#   make build          build the binary into ./bin
#   make docker-build   build the container image
#   make k8s-deploy     apply Kubernetes manifests (uses kustomize)
#   make smoke          start the server and exercise the API

BINARY      := metakube
PKG         := ./cmd/metakube
BIN_DIR     := bin
IMAGE       ?= metakube:latest
PORT        ?= 8080

VERSION     ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo dev)
COMMIT      ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)
BUILD_DATE  ?= $(shell date -u +%Y-%m-%dT%H:%M:%SZ)
LDFLAGS     := -s -w \
  -X github.com/openautonomyx/platform/internal/version.Version=$(VERSION) \
  -X github.com/openautonomyx/platform/internal/version.Commit=$(COMMIT) \
  -X github.com/openautonomyx/platform/internal/version.BuildDate=$(BUILD_DATE)

export GOTOOLCHAIN := local

.PHONY: all build run test cover vet fmt fmt-check tidy clean docker-build docker-run k8s-deploy k8s-delete smoke

all: fmt-check vet test build

build:
	@mkdir -p $(BIN_DIR)
	go build -trimpath -ldflags "$(LDFLAGS)" -o $(BIN_DIR)/$(BINARY) $(PKG)
	@echo "built $(BIN_DIR)/$(BINARY) ($(VERSION))"

run:
	go run $(PKG)

test:
	go test ./... -race -count=1

cover:
	go test ./... -coverprofile=coverage.out
	go tool cover -func=coverage.out | tail -1

vet:
	go vet ./...

fmt:
	gofmt -w .

fmt-check:
	@out=$$(gofmt -l .); if [ -n "$$out" ]; then echo "gofmt needed:"; echo "$$out"; exit 1; fi

clean:
	rm -rf $(BIN_DIR) dist coverage.out

docker-build:
	docker build \
	  --build-arg VERSION=$(VERSION) \
	  --build-arg COMMIT=$(COMMIT) \
	  --build-arg BUILD_DATE=$(BUILD_DATE) \
	  -t $(IMAGE) .

docker-run: docker-build
	docker run --rm -p $(PORT):8080 $(IMAGE)

k8s-deploy:
	kubectl apply -k deploy/k8s

k8s-delete:
	kubectl delete -k deploy/k8s

smoke: build
	@./scripts/smoke.sh
