import argparse
import json
import logging
import sys

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.services.job_service import job_stats
from app.services.sync_service import configured_sources, sync_all


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Jobs Aggregator command line interface")
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync_parser = subparsers.add_parser("sync", help="Run all configured connectors once")
    sync_parser.add_argument("--source", help="Only run one provider, token, or company")
    subparsers.add_parser("sources", help="List configured sources")
    subparsers.add_parser("status", help="Show database statistics")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    init_db()

    if args.command == "sync":
        sources = configured_sources(settings)
        if not any(source.get("configured") for source in sources):
            print(
                "No enabled sources are configured. Set THEIRSTACK_API_KEY or enable a direct "
                "ATS source in config/sources.yaml.",
                file=sys.stderr,
            )
            raise SystemExit(2)
        summaries = sync_all(settings=settings, source_filter=args.source)
        print(json.dumps([summary.to_dict() for summary in summaries], indent=2, default=str))
        raise SystemExit(1 if any(summary.status == "failed" for summary in summaries) else 0)

    if args.command == "sources":
        print(json.dumps(configured_sources(settings), indent=2))
        return

    with SessionLocal() as session:
        print(
            json.dumps(
                job_stats(session, hours=settings.posted_within_hours),
                indent=2,
                default=str,
            )
        )


if __name__ == "__main__":
    main()
