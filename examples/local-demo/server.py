"""A deterministic, loopback-only API for the documentation walkthrough."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

RECORDS = [
    {"id": number, "title": f"Item {number}", "updated_at": f"2026-01-0{number}"}
    for number in range(1, 6)
]


class Handler(BaseHTTPRequestHandler):
    """Serve the same five records with page-number pagination."""

    def do_GET(self):
        """Return one page of records."""
        self.respond(parse_qs(urlsplit(self.path).query))

    def do_POST(self):
        """Accept the pagination parameters as a JSON body, too."""
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            self.respond({key: [str(value)] for key, value in body.items()})
        except (ValueError, AttributeError):
            self.send_error(400, "Expected a JSON object")

    def respond(self, params):
        """Serialize the requested page with a known total."""
        if urlsplit(self.path).path != "/items":
            self.send_error(404)
            return
        try:
            page = int(params.get("page", [1])[0])
            per_page = int(params.get("per_page", [2])[0])
            if page < 1 or per_page < 1:
                raise ValueError
        except ValueError:
            self.send_error(400, "page and per_page must be positive integers")
            return
        start = (page - 1) * per_page
        body = json.dumps({"total": len(RECORDS), "items": RECORDS[start : start + per_page]})
        payload = body.encode("utf8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def create_server(port=8765):
    """Bind only the loopback interface; port 0 is useful for tests."""
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with create_server(args.port) as server:
        print(f"Demo API: http://127.0.0.1:{server.server_port}/items", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
