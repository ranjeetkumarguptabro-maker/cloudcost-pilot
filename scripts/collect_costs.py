#!/usr/bin/env python3
"""CLI script for collecting AWS Cost Explorer data and exporting to JSON."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

# Ensure project root is in sys.path when executed directly as a script
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.analyzer.cost_analyzer import CostAnalyzer
from app.aws.client import (
    AWSAuthenticationError,
    AWSClientError,
    create_cost_explorer_client,
    get_boto3_session,
    validate_aws_identity,
)
from app.aws.cost_explorer import get_cost_and_usage
from app.config import get_settings
from app.logging_config import get_logger, setup_logging
from app.reports.exporter import export_to_json

logger = get_logger(__name__)


def parse_iso_date(date_str: str) -> date:
    """Parse YYYY-MM-DD string into date object."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date format: '{date_str}'. Expected YYYY-MM-DD."
        ) from exc


def get_default_date_range(granularity: str) -> tuple[date, date]:
    """Calculate sensible default date ranges when not explicitly provided."""
    today = datetime.now(UTC).date()
    # End date in Cost Explorer is exclusive, so tomorrow includes today
    tomorrow = today + timedelta(days=1)

    if granularity == "DAILY":
        # Default to first day of current month through today
        start_date = today.replace(day=1)
        # If today is the 1st, fetch last 14 days for meaningful daily trend
        if start_date == today:
            start_date = today - timedelta(days=14)
        return start_date, tomorrow

    if granularity == "MONTHLY":
        # Default to 3 months back
        # Approximate 90 days back to first of month
        three_months_ago = today - timedelta(days=90)
        start_date = three_months_ago.replace(day=1)
        return start_date, tomorrow

    return today - timedelta(days=30), tomorrow


def build_parser() -> argparse.ArgumentParser:
    """Build command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="CloudCost Pilot - AWS Cost Explorer Collector",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--start",
        type=parse_iso_date,
        default=None,
        help="Start date in YYYY-MM-DD format (inclusive). Defaults to start of current month.",
    )
    parser.add_argument(
        "--end",
        type=parse_iso_date,
        default=None,
        help="End date in YYYY-MM-DD format (exclusive). Defaults to tomorrow (inclusive of today).",
    )
    parser.add_argument(
        "--granularity",
        choices=["DAILY", "MONTHLY"],
        default="DAILY",
        help="Cost granularity (DAILY or MONTHLY).",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="AWS CLI profile name (overrides AWS_PROFILE environment variable).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file destination. Defaults to data/costs_<granularity>_<start>_<end>.json.",
    )
    parser.add_argument(
        "--metric",
        type=str,
        default="UnblendedCost",
        help="Cost Explorer metric to query (UnblendedCost, BlendedCost, NetUnblendedCost, etc.).",
    )
    parser.add_argument(
        "--log-format",
        choices=["text", "json"],
        default="text",
        help="Log output format.",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level.",
    )
    return parser


def main() -> int:
    """Main execution flow for cost collector CLI."""
    parser = build_parser()
    args = parser.parse_args()

    # Configure logging
    setup_logging(level=args.log_level, log_format=args.log_format)
    settings = get_settings()

    granularity = args.granularity
    if args.start is not None and args.end is not None:
        start_date = args.start
        end_date = args.end
    elif args.start is not None:
        start_date = args.start
        _, default_end = get_default_date_range(granularity)
        end_date = default_end
    elif args.end is not None:
        default_start, _ = get_default_date_range(granularity)
        start_date = default_start
        end_date = args.end
    else:
        start_date, end_date = get_default_date_range(granularity)

    if start_date >= end_date:
        logger.error(
            "Invalid date range: start_date (%s) must be strictly earlier than end_date (%s).",
            start_date.isoformat(),
            end_date.isoformat(),
        )
        return 1

    profile = args.profile or settings.aws_profile

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        filename = f"costs_{granularity.lower()}_{start_date.isoformat()}_{end_date.isoformat()}.json"
        output_path = settings.data_dir / filename

    print("=" * 70)
    print(" CloudCost Pilot — AWS Cost Explorer Collector")
    print("=" * 70)
    print(f" Reporting Period: {start_date.isoformat()} to {end_date.isoformat()} (exclusive)")
    print(f" Granularity:      {granularity}")
    print(f" Metric:           {args.metric}")
    print(f" Profile:          {profile or 'Default Credential Chain'}")
    print(f" Output Target:    {output_path}")
    print("-" * 70)

    try:
        # 1. Establish AWS session and validate caller identity
        session = get_boto3_session(profile_name=profile)
        identity = validate_aws_identity(session)
        account_id = identity["account_id"]

        print(f" Connected Account: {account_id}")
        print(f" Caller Identity:   {identity['arn']}")
        print("-" * 70)

        # 2. Initialize Cost Explorer client (us-east-1)
        ce_client = create_cost_explorer_client(session)

        # 3. Retrieve cost and usage
        print(" Querying AWS Cost Explorer API...")
        result = get_cost_and_usage(
            client=ce_client,
            start_date=start_date,
            end_date_exclusive=end_date,
            granularity=granularity,
            metric=args.metric,
            account_id=account_id,
        )

        # 4. Perform analytics on collected data
        breakdown = CostAnalyzer.get_service_breakdown(result, top_n=5)

        # 5. Export result to JSON atomically
        export_payload = result.to_export_dict()
        saved_path = export_to_json(export_payload, output_path)

        # 6. Display summary
        print("\n" + "=" * 70)
        print(" COLLECTION SUMMARY")
        print("=" * 70)
        print(f" Total Recorded Cost: {result.total_cost:.4f} {result.currency}")
        print(f" Time Periods:        {len(result.results_by_time)}")
        if result.highest_cost_service:
            print(
                f" Highest Cost Service: {result.highest_cost_service[0]} "
                f"({result.highest_cost_service[1]:.4f} {result.currency})"
            )
        print("\n Top 5 Services by Spending:")
        for idx, item in enumerate(breakdown, 1):
            print(
                f"  {idx}. {item.service_name:<42} "
                f"{item.amount:>10.4f} {item.currency} ({item.percentage_of_total:>5.1f}%)"
            )

        print("-" * 70)
        print(f" Results successfully exported to: {saved_path}")
        print("=" * 70)
        return 0

    except AWSAuthenticationError as exc:
        print(f"\n[ERROR] Authentication failed: {exc}", file=sys.stderr)
        return 1
    except AWSClientError as exc:
        print(f"\n[ERROR] AWS API call failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        logger.exception("Unexpected error during cost collection: %s", exc)
        print(f"\n[ERROR] Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
