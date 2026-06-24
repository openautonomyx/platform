"""A minimal discoverable ard agent — a *skill server*.

Serves its A2A agent card at /.well-known/agent.json (so the ard registry can
discover it) plus a tiny `echo` skill. Stdlib only; `ard` provides the card.

    pip install ard
    python agent.py        # http://127.0.0.1:8080
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ard import agent_card
from ard.card import WELL_KNOWN_PATH

CARD = agent_card(
    name="echo-agent",
    description="Echoes text back — a sample ard skill server.",
    url="http://localhost:8080",
    version="0.1.0",
    kind="skill",
    skills=[{"id": "echo", "name": "Echo", "description": "Return the input text", "tags": ["text"]}],
)


class Handler(BaseHTTPRequestHandler):
    def _json(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == WELL_KNOWN_PATH:
            self._json(200, CARD.to_dict())
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/skills/echo":
            n = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(n) or b"{}")
            self._json(200, {"echo": payload.get("text", "")})
        else:
            self._json(404, {"error": "no such skill"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"echo-agent on http://127.0.0.1:8080  (GET {WELL_KNOWN_PATH} · POST /skills/echo)")
    ThreadingHTTPServer(("127.0.0.1", 8080), Handler).serve_forever()
