# syntax=docker/dockerfile:1

# ---- build stage ----
FROM golang:1.24 AS build
WORKDIR /src

# The module has no third-party dependencies, so only go.mod is needed for a
# cached, fully offline build.
COPY go.mod ./
COPY cmd ./cmd
COPY internal ./internal

ARG VERSION=dev
ARG COMMIT=dev
ARG BUILD_DATE=unknown

RUN CGO_ENABLED=0 GOOS=linux go build -trimpath \
    -ldflags "-s -w \
      -X github.com/openautonomyx/platform/internal/version.Version=${VERSION} \
      -X github.com/openautonomyx/platform/internal/version.Commit=${COMMIT} \
      -X github.com/openautonomyx/platform/internal/version.BuildDate=${BUILD_DATE}" \
    -o /out/metakube ./cmd/metakube

# ---- runtime stage ----
# distroless/static gives us a minimal, non-root image with no shell or package
# manager, shrinking the attack surface.
FROM gcr.io/distroless/static-debian12:nonroot

LABEL org.opencontainers.image.title="MetaKube" \
      org.opencontainers.image.description="Kubernetes-native Decision Intelligence Platform" \
      org.opencontainers.image.source="https://github.com/openautonomyx/platform"

WORKDIR /
COPY --from=build /out/metakube /metakube

EXPOSE 8080
USER nonroot:nonroot
ENTRYPOINT ["/metakube"]
