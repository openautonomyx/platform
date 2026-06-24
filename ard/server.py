"""Minimal stdlib HTTP server exposing the discovery API (``ard serve``)."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .api import DiscoveryApi
from .registry import Registry


def make_handler(api: DiscoveryApi):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ard-discovery/0.1"

        def _read_body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if not n:
                return None
            raw = self.rfile.read(n)
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return _INVALID

        def _respond(self, status: int, data) -> None:
            payload = b"" if data is None else json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if payload:
                self.wfile.write(payload)

        def do_GET(self):
            self._respond(*api.handle("GET", self.path))

        def do_POST(self):
            body = self._read_body()
            if body is _INVALID:
                self._respond(400, {"error": "invalid JSON body"})
                return
            self._respond(*api.handle("POST", self.path, body))

        def do_DELETE(self):
            self._respond(*api.handle("DELETE", self.path))

        def log_message(self, *args):  # quiet by default
            pass

    return Handler


_INVALID = object()


def serve(registry: Registry | None = None, host: str = "127.0.0.1", port: int = 8080) -> None:
    api = DiscoveryApi(registry)
    httpd = ThreadingHTTPServer((host, port), make_handler(api))
    print(f"ard discovery registry → http://{host}:{port}  (GET /agents · POST /agents · GET /healthz)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()
