from __future__ import annotations

import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from aggregator.config import ROOT


def serve(port: int = 8000) -> None:
    web = ROOT / "docs"
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(web))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"Dashboard: http://127.0.0.1:{port}")
    httpd.serve_forever()
