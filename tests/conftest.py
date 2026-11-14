"""Pytest shared fixtures and mock data for CloudCost Pilot."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from app.aws.cost_explorer import CostCollectionResult, PeriodCost, ServiceCost


@pytest.fixture
def mock_sts_response() -> dict[str, Any]:
    """Sample valid STS get_caller_identity response."""
    return {
        "UserId": "AROA123456789EXAMPLE:session-name",
        "Account": "123456789012",
        "Arn": "arn:aws:sts::123456789012:assumed-role/CloudCostPilotRole/session",
        "ResponseMetadata": {"HTTPStatusCode": 200},
    }


@pytest.fixture
def mock_ce_daily_response_page_1() -> dict[str, Any]:
    """Sample AWS Cost Explorer GetCostAndUsage page 1 with NextPageToken."""
    return {
        "DimensionValueAttributes": [],
        "GroupDefinitions": [{"Type": "DIMENSION", "Key": "SERVICE"}],
        "NextPageToken": "token-page-2-xyz",
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2026-11-01", "End": "2026-11-02"},
                "Total": {},
                "Groups": [
                    {
                        "Keys": ["Amazon Elastic Compute Cloud - Compute"],
                        "Metrics": {
                            "UnblendedCost": {"Amount": "45.500000", "Unit": "USD"}
                        },
                    },
                    {
                        "Keys": ["Amazon Simple Storage Service"],
                        "Metrics": {
                            "UnblendedCost": {"Amount": "8.250000", "Unit": "USD"}
                        },
                    },
                ],
                "Estimated": False,
            }
        ],
        "ResponseMetadata": {"HTTPStatusCode": 200},
    }


@pytest.fixture
def mock_ce_daily_response_page_2() -> dict[str, Any]:
    """Sample AWS Cost Explorer GetCostAndUsage final page without NextPageToken."""
    return {
        "DimensionValueAttributes": [],
        "GroupDefinitions": [{"Type": "DIMENSION", "Key": "SERVICE"}],
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2026-11-02", "End": "2026-11-03"},
                "Total": {},
                "Groups": [
                    {
                        "Keys": ["Amazon Elastic Compute Cloud - Compute"],
                        "Metrics": {
                            "UnblendedCost": {"Amount": "42.000000", "Unit": "USD"}
                        },
                    },
                    {
                        "Keys": ["Amazon Relational Database Service"],
                        "Metrics": {
                            "UnblendedCost": {"Amount": "22.100000", "Unit": "USD"}
                        },
                    },
                    {
                        "Keys": ["AWS Lambda"],
                        "Metrics": {
                            "UnblendedCost": {"Amount": "3.150000", "Unit": "USD"}
                        },
                    },
                ],
                "Estimated": False,
            }
        ],
        "ResponseMetadata": {"HTTPStatusCode": 200},
    }


@pytest.fixture
def sample_collection_result() -> CostCollectionResult:
    """Pre-built CostCollectionResult domain object for analyzer testing."""
    return CostCollectionResult(
        collected_at="2026-11-14T10:00:00+00:00",
        account_id="123456789012",
        start_date="2026-11-01",
        end_date_exclusive="2026-11-03",
        granularity="DAILY",
        metric="UnblendedCost",
        currency="USD",
        total_cost=Decimal("121.00"),
        service_totals={
            "Amazon Elastic Compute Cloud - Compute": Decimal("87.50"),
            "Amazon Relational Database Service": Decimal("22.10"),
            "Amazon Simple Storage Service": Decimal("8.25"),
            "AWS Lambda": Decimal("3.15"),
        },
        highest_cost_service=(
            "Amazon Elastic Compute Cloud - Compute",
            Decimal("87.50"),
        ),
        results_by_time=[
            PeriodCost(
                start_date="2026-11-01",
                end_date_exclusive="2026-11-02",
                total_amount=Decimal("53.75"),
                currency="USD",
                services=[
                    ServiceCost(
                        service_name="Amazon Elastic Compute Cloud - Compute",
                        amount=Decimal("45.50"),
                        currency="USD",
                    ),
                    ServiceCost(
                        service_name="Amazon Simple Storage Service",
                        amount=Decimal("8.25"),
                        currency="USD",
                    ),
                ],
            ),
            PeriodCost(
                start_date="2026-11-02",
                end_date_exclusive="2026-11-03",
                total_amount=Decimal("67.25"),
                currency="USD",
                services=[
                    ServiceCost(
                        service_name="Amazon Elastic Compute Cloud - Compute",
                        amount=Decimal("42.00"),
                        currency="USD",
                    ),
                    ServiceCost(
                        service_name="Amazon Relational Database Service",
                        amount=Decimal("22.10"),
                        currency="USD",
                    ),
                    ServiceCost(
                        service_name="AWS Lambda",
                        amount=Decimal("3.15"),
                        currency="USD",
                    ),
                ],
            ),
        ],
        raw_results=[],
    )
