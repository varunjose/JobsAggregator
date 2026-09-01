from __future__ import annotations

import argparse

from aggregator.pipeline import run_ingest
from aggregator.serve import serve


def main() -> None:
    parser = argparse.ArgumentParser(prog="aggregator", description="US jobs aggregator")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("ingest", help="Pull jobs from ATS boards and market APIs")
    serve_p = sub.add_parser("serve", help="Serve the local dashboard")
    serve_p.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.cmd == "ingest":
        meta = run_ingest()
        print(f"Wrote {meta.get('kept_jobs')} jobs")
        return
    if args.cmd == "serve":
        serve(args.port)
        return
    parser.print_help()
