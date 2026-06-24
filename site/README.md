# Decision Intelligence Console — static build

This folder is a fully static build of the console, published to GitHub Pages
by `.github/workflows/pages.yml`.

The `dip` decision engine is ported to run **entirely in the browser**
(`engine.js`), so there is no backend: `DIP.handle(method, path, body)` mirrors
the Python `app.api.Api.handle` exactly (same routes, JSON shapes and error
envelopes), and `app.js` calls it in place of `fetch()`.

| File | Role |
| --- | --- |
| `index.html` | Page shell (relative asset paths for a project Pages site) |
| `engine.js` | In-browser port of `dip` + registry + serialization + API router |
| `app.js` | The UI (unchanged except `api()` → `DIP.handle`) |
| `style.css` | Styles (verbatim from `app/static/style.css`) |

Parity with the Python engine is enforced by `site-tests/verify-engine.cjs`
(32 checks), which runs in CI before every deploy.

## Local preview

```bash
cd site && python -m http.server 8000   # then open http://localhost:8000
```

## Deploy

Pushing changes under `site/` to the `claude/zen-darwin-tr3ksk` branch triggers
the Pages workflow (verify parity → upload → deploy). GitHub Pages must be
enabled once with **Settings → Pages → Source: GitHub Actions**.
