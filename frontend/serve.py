"""
Serve the static Code Explorer UI.

From the Lab5 directory:
    python3 frontend/serve.py

Listens on 127.0.0.1:5500. Caching is disabled so this page is not
confused with a lab that previously used the same URL.
"""

import http.server
import os
import sys

HOST = "127.0.0.1"
PORT = 5500

_FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))


class FrontendHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=_FRONTEND_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        super().end_headers()

    def do_GET(self):
        self._drop_conditional_headers()
        return super().do_GET()

    def do_HEAD(self):
        self._drop_conditional_headers()
        return super().do_HEAD()

    def _drop_conditional_headers(self):
        """Avoid 304 responses that reuse another tree's cached index.html."""
        for name in ("If-Modified-Since", "If-None-Match"):
            if name in self.headers:
                del self.headers[name]


def main():
    server = http.server.ThreadingHTTPServer((HOST, PORT), FrontendHandler)
    print("Serving:   {}".format(_FRONTEND_DIR), flush=True)
    print("Frontend:  http://{}:{}/".format(HOST, PORT), flush=True)
    print("REST API:  http://127.0.0.1:8000", flush=True)
    print("Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
