"""Unit tests for collect_costs CLI script."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from app.aws.client import AWSAuthenticationError
from scripts.collect_costs import (
    build_parser,
    get_default_date_range,
    main,
    parse_iso_date,
)


def test_parse_iso_date_valid():
    """Verify ISO date parsing."""
    parsed = parse_iso_date("2026-11-14")
    assert parsed == date(2026, 11, 14)


def test_parse_iso_date_invalid():
    """Verify invalid format raises ArgumentTypeError."""
    with pytest.raises(argparse.ArgumentTypeError):
        parse_iso_date("14-11-2026")


def test_get_default_date_range_daily():
    """Verify daily default date range has start < end."""
    start, end = get_default_date_range("DAILY")
    assert start < end


def test_get_default_date_range_monthly():
    """Verify monthly default date range has start < end."""
    start, end = get_default_date_range("MONTHLY")
    assert start < end


def test_build_parser_defaults():
    """Verify parser default values."""
    parser = build_parser()
    args = parser.parse_args([])
    assert args.granularity == "DAILY"
    assert args.metric == "UnblendedCost"
    assert args.profile is None


def test_build_parser_custom_args():
    """Verify parser correctly captures specified flags."""
    parser = build_parser()
    args = parser.parse_args(
        [
            "--start",
            "2026-11-01",
            "--end",
            "2026-11-14",
            "--granularity",
            "MONTHLY",
            "--profile",
            "test-profile",
            "--output",
            "custom.json",
        ]
    )
    assert args.start == date(2026, 11, 1)
    assert args.end == date(2026, 11, 14)
    assert args.granularity == "MONTHLY"
    assert args.profile == "test-profile"
    assert args.output == "custom.json"


@patch("scripts.collect_costs.get_boto3_session")
@patch("scripts.collect_costs.validate_aws_identity")
@patch("scripts.collect_costs.create_cost_explorer_client")
@patch("scripts.collect_costs.get_cost_and_usage")
@patch("scripts.collect_costs.export_to_json")
def test_main_cli_success(
    mock_export,
    mock_get_cost,
    _mock_create_ce,
    mock_validate_id,
    _mock_get_session,
    sample_collection_result,
    tmp_path: Path,
):
    """Verify CLI main function executes end-to-end and returns 0 exit code."""
    mock_validate_id.return_value = {
        "account_id": "123456789012",
        "arn": "arn:aws:iam::123456789012:user/dev",
        "user_id": "AIDAZZZ",
    }
    mock_get_cost.return_value = sample_collection_result
    output_file = tmp_path / "costs.json"
    mock_export.return_value = output_file

    test_args = [
        "collect_costs.py",
        "--start",
        "2026-11-01",
        "--end",
        "2026-11-03",
        "--granularity",
        "DAILY",
        "--output",
        str(output_file),
    ]

    with patch("sys.argv", test_args):
        exit_code = main()

    assert exit_code == 0
    mock_validate_id.assert_called_once()
    mock_get_cost.assert_called_once()
    mock_export.assert_called_once()


@patch("scripts.collect_costs.get_boto3_session")
def test_main_cli_auth_failure(mock_get_session):
    """Verify CLI returns exit code 1 when AWS authentication fails."""
    mock_get_session.side_effect = AWSAuthenticationError("Missing credentials")

    test_args = ["collect_costs.py", "--start", "2026-11-01", "--end", "2026-11-03"]
    with patch("sys.argv", test_args):
        exit_code = main()

    assert exit_code == 1


def test_main_cli_inverted_dates():
    """Verify CLI returns exit code 1 when start date is later than end date."""
    test_args = ["collect_costs.py", "--start", "2026-11-10", "--end", "2026-11-01"]
    with patch("sys.argv", test_args):
        exit_code = main()

    assert exit_code == 1
