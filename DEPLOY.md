# Deploying MetaKube to the cloud

MetaKube ships as a single non-root distroless container (see `Dockerfile`) that
listens on `$PORT` (default `8080`) and exposes `/healthz` (liveness) and
`/readyz` (readiness). That makes it deployable on any container host. Configs
for three popular clouds are included; each gives you a public HTTPS URL and
supports a custom domain.

| Cloud | Config | Runs the real Go service? |
|---|---|---|
| Fly.io | [`fly.toml`](fly.toml) | ✅ |
| Render | [`render.yaml`](render.yaml) | ✅ |
| Google Cloud Run | [`deploy/cloudrun/service.yaml`](deploy/cloudrun/service.yaml) | ✅ |
| Kubernetes | [`deploy/k8s/`](deploy/k8s) | ✅ |

> You run these deploys (they create resources under your own cloud accounts).
> Each platform builds the repo `Dockerfile`.

## Fly.io

```bash
fly launch --no-deploy --copy-config   # first time: creates the app from fly.toml
fly deploy
fly open                                # opens https://metakube.fly.dev
# Custom domain:
fly certs add api.your-domain.com       # then add the printed A/AAAA/CNAME records
```

## Render

1. Push this repo to GitHub.
2. Render dashboard → **New + → Blueprint** → select the repo (`render.yaml` is detected).
3. Render builds the Dockerfile and deploys a public web service with a
   `*.onrender.com` URL.
4. **Settings → Custom Domains** → add your domain and create the shown CNAME.

## Google Cloud Run

```bash
# One-shot from source (Cloud Build uses the repo Dockerfile):
gcloud run deploy metakube --source . --region us-central1 --allow-unauthenticated

# Or build, push, and apply the declarative manifest:
gcloud builds submit --tag us-central1-docker.pkg.dev/PROJECT_ID/metakube/metakube:latest
gcloud run services replace deploy/cloudrun/service.yaml --region us-central1

# Custom domain:
gcloud run domain-mappings create --service metakube --domain api.your-domain.com --region us-central1
```

## Configuration

All clouds read the same environment variables (see the README for the full
list). The most common:

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8080` | Listen port (Cloud Run sets this automatically) |
| `LOG_LEVEL` | `info` | `debug` / `info` / `warn` / `error` |
| `SHUTDOWN_TIMEOUT_SECONDS` | `15` | Graceful drain on `SIGTERM` (clean rolling deploys) |

## Notes

- MetaKube keeps state **in memory** (decision runs, audit log, agents). For a
  single instance this is fine; if you scale to multiple replicas, treat each as
  independent or front them with a shared store (a future enhancement).
- Liveness uses `/healthz`; routing/readiness uses `/readyz`. Point each
  platform's health check at the appropriate one (the configs already do).
