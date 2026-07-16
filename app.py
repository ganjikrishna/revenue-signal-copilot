"""Small standard-library web app; business logic lives in copilot.py."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from copilot import analyze

ROOT = Path(__file__).parent


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        routes = {
            "/": ("web/index.html", "text/html; charset=utf-8"),
            "/app.js": ("web/app.js", "application/javascript; charset=utf-8"),
            "/styles.css": ("web/styles.css", "text/css; charset=utf-8"),
            "/demo/lead.json": ("demo/lead.json", "application/json; charset=utf-8"),
            "/demo/leads.json": ("demo/leads.json", "application/json; charset=utf-8"),
        }
        if self.path not in routes:
            self._send(404, b'{"error":"not found"}', "application/json")
            return
        path, content_type = routes[self.path]
        self._send(200, (ROOT / path).read_bytes(), content_type)

    def do_POST(self) -> None:
        if self.path != "/api/analyze":
            self._send(404, b'{"error":"not found"}', "application/json")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 20_000:
                raise ValueError("request body must be between 1 and 20,000 bytes")
            data = json.loads(self.rfile.read(length))
            result = analyze(data)
            self._send(200, json.dumps(result).encode(), "application/json")
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, json.dumps({"error": str(exc)}).encode(), "application/json")

    def log_message(self, format: str, *args: object) -> None:
        print(f"[revenue-copilot] {format % args}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"Revenue Signal Copilot: http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
