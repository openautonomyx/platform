"""HTTP wiring for the console, built on the standard library only.

This is the single module that knows about sockets. It adapts the stdlib
:class:`~http.server.BaseHTTPRequestHandler` to the transport-independent
:class:`~app.api.Api`, so there are no third-party dependencies to install.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .api import Api, Response


def make_handler(api: Api) -> type[BaseHTTPRequestHandler]:
    """Build a request handler class bound to ``api``."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "DIPConsole/0.1"
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:  # noqa: N802 — name mandated by BaseHTTPRequestHandler
            self._dispatch("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch("POST")

        def _dispatch(self, method: str) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            self._write(api.handle(method, self.path, body))

        def _write(self, resp: Response) -> None:
            self.send_response(resp.status)
            self.send_header("Content-Type", resp.content_type)
            self.send_header("Content-Length", str(len(resp.body)))
            self.end_headers()
            self.wfile.write(resp.body)

        def log_message(self, *_args: object) -> None:
            # Quiet by default; subclass/override if you want access logs.
            pass

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8000, api: Api | None = None) -> None:
    """Run the console until interrupted (blocking)."""
    api = api or Api()
    httpd = ThreadingHTTPServer((host, port), make_handler(api))
    print(f"DIP console serving on http://{host}:{port}  (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        httpd.server_close()
