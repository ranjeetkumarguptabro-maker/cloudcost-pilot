"""Unit tests for AWS Cost Explorer data collection and pagination."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import boto3
import pytest
from botocore.stub import Stubber

from app.aws.client import AWSClientError
from app.aws.cost_explorer import (
    get_cost_and_usage,
    validate_date_range,
    validate_granularity,
)


def test_validate_date_range_valid():
    """Verify valid date ranges pass without exception."""
    validate_date_range(date(2026, 11, 1), date(2026, 11, 2))
    validate_date_range(date(2026, 1, 1), date(2026, 12, 31))


def test_validate_date_range_equal_dates():
    """Verify equal start and end dates raise ValueError (since end is exclusive)."""
    with pytest.raises(ValueError) as exc:
        validate_date_range(date(2026, 11, 1), date(2026, 11, 1))
    assert "must be strictly earlier than" in str(exc.value)


def test_validate_date_range_inverted_dates():
    """Verify inverted dates raise ValueError."""
    with pytest.raises(ValueError) as exc:
        validate_date_range(date(2026, 11, 10), date(2026, 11, 1))
    assert "must be strictly earlier than" in str(exc.value)


def test_validate_granularity():
    """Verify granularity validation for supported and unsupported values."""
    validate_granularity("DAILY")
    validate_granularity("MONTHLY")

    with pytest.raises(ValueError) as exc:
        validate_granularity("HOURLY")
    assert "Invalid granularity" in str(exc.value)


def test_get_cost_and_usage_single_page(mock_ce_daily_response_page_2):
    """Verify single-page cost collection parses dimensions and calculates totals."""
    session = boto3.Session(region_name="us-east-1")
    ce_client = session.client("ce")

    expected_params = {
        "TimePeriod": {"Start": "2026-11-02", "End": "2026-11-03"},
        "Granularity": "DAILY",
        "Metrics": ["UnblendedCost"],
        "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
    }

    with Stubber(ce_client) as stubber:
        stubber.add_response(
            "get_cost_and_usage",
            mock_ce_daily_response_page_2,
            expected_params,
        )

        result = get_cost_and_usage(
            client=ce_client,
            start_date=date(2026, 11, 2),
            end_date_exclusive=date(2026, 11, 3),
            granularity="DAILY",
            account_id="123456789012",
        )

    assert result.account_id == "123456789012"
    assert result.start_date == "2026-11-02"
    assert result.end_date_exclusive == "2026-11-03"
    assert result.granularity == "DAILY"
    assert result.currency == "USD"
    # Total = 42.00 + 22.10 + 3.15 = 67.25
    assert result.total_cost == Decimal("67.25")
    assert len(result.results_by_time) == 1

    # Highest cost service
    assert result.highest_cost_service is not None
    assert result.highest_cost_service[0] == "Amazon Elastic Compute Cloud - Compute"
    assert result.highest_cost_service[1] == Decimal("42.00")

    # Service totals
    assert result.service_totals["Amazon Elastic Compute Cloud - Compute"] == Decimal(
        "42.00"
    )
    assert result.service_totals["Amazon Relational Database Service"] == Decimal(
        "22.10"
    )
    assert result.service_totals["AWS Lambda"] == Decimal("3.15")


def test_get_cost_and_usage_pagination(
    mock_ce_daily_response_page_1,
    mock_ce_daily_response_page_2,
):
    """Verify multi-page paginated Cost Explorer responses are aggregated."""
    session = boto3.Session(region_name="us-east-1")
    ce_client = session.client("ce")

    param_page_1 = {
        "TimePeriod": {"Start": "2026-11-01", "End": "2026-11-03"},
        "Granularity": "DAILY",
        "Metrics": ["UnblendedCost"],
        "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
    }

    param_page_2 = {
        "TimePeriod": {"Start": "2026-11-01", "End": "2026-11-03"},
        "Granularity": "DAILY",
        "Metrics": ["UnblendedCost"],
        "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
        "NextPageToken": "token-page-2-xyz",
    }

    with Stubber(ce_client) as stubber:
        stubber.add_response(
            "get_cost_and_usage", mock_ce_daily_response_page_1, param_page_1
        )
        stubber.add_response(
            "get_cost_and_usage", mock_ce_daily_response_page_2, param_page_2
        )

        result = get_cost_and_usage(
            client=ce_client,
            start_date=date(2026, 11, 1),
            end_date_exclusive=date(2026, 11, 3),
            granularity="DAILY",
        )

    # Page 1 = 45.50 + 8.25 = 53.75
    # Page 2 = 42.00 + 22.10 + 3.15 = 67.25
    # Combined total = 121.00
    assert result.total_cost == Decimal("121.00")
    assert len(result.results_by_time) == 2
    # Combined EC2 = 45.50 + 42.00 = 87.50
    assert result.service_totals["Amazon Elastic Compute Cloud - Compute"] == Decimal(
        "87.50"
    )
    assert result.highest_cost_service == (
        "Amazon Elastic Compute Cloud - Compute",
        Decimal("87.50"),
    )


def test_get_cost_and_usage_access_denied():
    """Verify AccessDeniedException raises AWSClientError with permission guidance."""
    session = boto3.Session(region_name="us-east-1")
    ce_client = session.client("ce")

    with Stubber(ce_client) as stubber:
        stubber.add_client_error(
            "get_cost_and_usage",
            service_error_code="AccessDeniedException",
            service_message="User is not authorized to perform ce:GetCostAndUsage",
        )

        with pytest.raises(AWSClientError) as exc:
            get_cost_and_usage(
                client=ce_client,
                start_date=date(2026, 11, 1),
                end_date_exclusive=date(2026, 11, 2),
            )

    assert "Access Denied" in str(exc.value)
    assert "ce:GetCostAndUsage" in str(exc.value)


def test_get_cost_and_usage_data_unavailable():
    """Verify DataUnavailableException provides explanation of AWS billing delays."""
    session = boto3.Session(region_name="us-east-1")
    ce_client = session.client("ce")

    with Stubber(ce_client) as stubber:
        stubber.add_client_error(
            "get_cost_and_usage",
            service_error_code="DataUnavailableException",
            service_message="Data is not ready yet",
        )

        with pytest.raises(AWSClientError) as exc:
            get_cost_and_usage(
                client=ce_client,
                start_date=date(2026, 11, 1),
                end_date_exclusive=date(2026, 11, 2),
            )

    assert "Data Unavailable" in str(exc.value)


def test_to_export_dict_structure(sample_collection_result):
    """Verify exported dictionary maintains string decimals and correct fields."""
    export_dict = sample_collection_result.to_export_dict()

    assert export_dict["account_id"] == "123456789012"
    assert export_dict["total_cost"] == "121.00"
    assert export_dict["currency"] == "USD"
    assert (
        export_dict["service_totals"]["Amazon Elastic Compute Cloud - Compute"]
        == "87.50"
    )
    assert export_dict["highest_cost_service"] == {
        "service": "Amazon Elastic Compute Cloud - Compute",
        "amount": "87.50",
    }
    assert len(export_dict["results_by_time"]) == 2
