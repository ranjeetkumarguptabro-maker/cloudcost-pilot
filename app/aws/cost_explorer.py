"""AWS Cost Explorer client and cost collection functions."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

from app.aws.client import AWSClientError
from app.logging_config import get_logger

logger = get_logger(__name__)

SUPPORTED_GRANULARITIES = ("DAILY", "MONTHLY")
DEFAULT_METRIC = "UnblendedCost"


class ServiceCost(BaseModel):
    """Cost breakdown for a specific AWS service."""

    service_name: str
    amount: Decimal = Field(
        description="Decimal cost amount to prevent floating-point inaccuracy"
    )
    currency: str


class PeriodCost(BaseModel):
    """Aggregated costs for a single time period (day or month)."""

    start_date: str
    end_date_exclusive: str
    total_amount: Decimal
    currency: str
    services: list[ServiceCost]


class CostCollectionResult(BaseModel):
    """Normalized response from Cost Explorer collection."""

    collected_at: str
    account_id: str | None
    start_date: str
    end_date_exclusive: str
    granularity: str
    metric: str
    currency: str
    total_cost: Decimal
    service_totals: dict[str, Decimal]
    highest_cost_service: tuple[str, Decimal] | None
    results_by_time: list[PeriodCost]
    raw_results: list[dict[str, Any]]

    def to_export_dict(self) -> dict[str, Any]:
        """Convert result to JSON-serializable dictionary with strings for Decimals."""
        return {
            "collected_at": self.collected_at,
            "account_id": self.account_id,
            "start_date": self.start_date,
            "end_date_exclusive": self.end_date_exclusive,
            "granularity": self.granularity,
            "metric": self.metric,
            "currency": self.currency,
            "total_cost": str(self.total_cost),
            "service_totals": {k: str(v) for k, v in self.service_totals.items()},
            "highest_cost_service": (
                {
                    "service": self.highest_cost_service[0],
                    "amount": str(self.highest_cost_service[1]),
                }
                if self.highest_cost_service
                else None
            ),
            "results_by_time": [
                {
                    "start_date": p.start_date,
                    "end_date_exclusive": p.end_date_exclusive,
                    "total_amount": str(p.total_amount),
                    "currency": p.currency,
                    "services": [
                        {
                            "service_name": s.service_name,
                            "amount": str(s.amount),
                            "currency": s.currency,
                        }
                        for s in p.services
                    ],
                }
                for p in self.results_by_time
            ],
            "raw_results": self.raw_results,
        }


def validate_date_range(start_date: date, end_date_exclusive: date) -> None:
    """Validate that start_date is strictly before end_date_exclusive."""
    if start_date >= end_date_exclusive:
        raise ValueError(
            f"start_date ({start_date.isoformat()}) must be strictly earlier than "
            f"end_date_exclusive ({end_date_exclusive.isoformat()}). "
            "Note that AWS Cost Explorer end date is exclusive."
        )


def validate_granularity(granularity: str) -> None:
    """Validate that granularity is supported by AWS Cost Explorer."""
    if granularity not in SUPPORTED_GRANULARITIES:
        raise ValueError(
            f"Invalid granularity '{granularity}'. "
            f"Supported values: {SUPPORTED_GRANULARITIES}"
        )


def get_cost_and_usage(
    client: Any,
    start_date: date,
    end_date_exclusive: date,
    granularity: str = "DAILY",
    metric: str = DEFAULT_METRIC,
    account_id: str | None = None,
) -> CostCollectionResult:
    """Retrieve AWS cost and usage information from Cost Explorer.

    Handles pagination, dimension grouping by SERVICE, data validation,
    and decimal normalization.

    Args:
        client: Boto3 Cost Explorer client.
        start_date: Inclusive start date.
        end_date_exclusive: Exclusive end date.
        granularity: 'DAILY' or 'MONTHLY'.
        metric: Cost metric to retrieve, defaults to 'UnblendedCost'.
        account_id: Optional AWS account ID for tagging metadata.

    Returns:
        CostCollectionResult containing normalized cost breakdowns.

    Raises:
        ValueError: If dates or granularity are invalid.
        AWSClientError: If the AWS Cost Explorer API call fails.
    """
    validate_date_range(start_date, end_date_exclusive)
    validate_granularity(granularity)

    logger.info(
        "Requesting AWS Cost Explorer data: %s to %s (Granularity: %s, Metric: %s)",
        start_date.isoformat(),
        end_date_exclusive.isoformat(),
        granularity,
        metric,
    )

    request_params: dict[str, Any] = {
        "TimePeriod": {
            "Start": start_date.isoformat(),
            "End": end_date_exclusive.isoformat(),
        },
        "Granularity": granularity,
        "Metrics": [metric],
        "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
    }

    raw_results: list[dict[str, Any]] = []
    page_count = 0

    try:
        while True:
            page_count += 1
            logger.debug("Fetching Cost Explorer page %d...", page_count)
            response = client.get_cost_and_usage(**request_params)

            results_by_time = response.get("ResultsByTime", [])
            raw_results.extend(results_by_time)

            next_page_token = response.get("NextPageToken")
            if not next_page_token:
                break
            request_params["NextPageToken"] = next_page_token

    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "Unknown")
        error_msg = exc.response.get("Error", {}).get("Message", str(exc))

        if error_code == "AccessDeniedException":
            msg = (
                f"AWS Cost Explorer Access Denied [{error_code}]: {error_msg}. "
                "Ensure your IAM identity has 'ce:GetCostAndUsage' permissions "
                "and that Cost Explorer is enabled in your AWS billing console."
            )
        elif error_code == "DataUnavailableException":
            msg = (
                f"AWS Cost Explorer Data Unavailable [{error_code}]: {error_msg}. "
                "Cost Explorer data may not be available for the requested period yet "
                "(AWS updates billing data at least once every 24 hours)."
            )
        elif error_code == "LimitExceededException":
            msg = f"AWS Cost Explorer rate limit exceeded [{error_code}]: {error_msg}"
        else:
            msg = f"AWS Cost Explorer API error [{error_code}]: {error_msg}"

        logger.error(msg)
        raise AWSClientError(msg) from exc

    logger.info(
        "Successfully retrieved %d time period record(s) across %d page(s) "
        "from Cost Explorer.",
        len(raw_results),
        page_count,
    )

    # Normalize response into typed domain models
    return _normalize_cost_results(
        raw_results=raw_results,
        account_id=account_id,
        start_date=start_date,
        end_date_exclusive=end_date_exclusive,
        granularity=granularity,
        metric=metric,
    )


def _normalize_cost_results(
    raw_results: list[dict[str, Any]],
    account_id: str | None,
    start_date: date,
    end_date_exclusive: date,
    granularity: str,
    metric: str,
) -> CostCollectionResult:
    """Normalize raw Cost Explorer ResultsByTime into CostCollectionResult."""
    period_costs: list[PeriodCost] = []
    overall_service_totals: dict[str, Decimal] = {}
    total_cost = Decimal("0.0")
    detected_currency = "USD"

    for time_entry in raw_results:
        time_period = time_entry.get("TimePeriod", {})
        period_start = time_period.get("Start", "")
        period_end = time_period.get("End", "")

        period_services: list[ServiceCost] = []
        period_total = Decimal("0.0")

        groups = time_entry.get("Groups", [])
        for group in groups:
            keys = group.get("Keys", [])
            service_name = keys[0] if keys else "Unknown Service"

            metrics_data = group.get("Metrics", {}).get(metric, {})
            amount_str = metrics_data.get("Amount", "0")
            currency = metrics_data.get("Unit", detected_currency)
            detected_currency = currency

            try:
                amount_decimal = Decimal(amount_str)
            except Exception:
                logger.warning(
                    "Invalid cost amount '%s' for service '%s'",
                    amount_str,
                    service_name,
                )
                amount_decimal = Decimal("0.0")

            period_services.append(
                ServiceCost(
                    service_name=service_name,
                    amount=amount_decimal,
                    currency=currency,
                )
            )
            period_total += amount_decimal
            overall_service_totals[service_name] = (
                overall_service_totals.get(service_name, Decimal("0.0"))
                + amount_decimal
            )

        # Sort services in period descending by amount
        period_services.sort(key=lambda s: s.amount, reverse=True)

        period_costs.append(
            PeriodCost(
                start_date=period_start,
                end_date_exclusive=period_end,
                total_amount=period_total,
                currency=detected_currency,
                services=period_services,
            )
        )
        total_cost += period_total

    # Determine highest cost service
    highest_cost_service: tuple[str, Decimal] | None = None
    if overall_service_totals:
        highest_cost_service = max(
            overall_service_totals.items(), key=lambda item: item[1]
        )

    # Sort overall service totals descending
    sorted_service_totals = dict(
        sorted(overall_service_totals.items(), key=lambda item: item[1], reverse=True)
    )

    now_utc = datetime.now(UTC).isoformat()

    return CostCollectionResult(
        collected_at=now_utc,
        account_id=account_id,
        start_date=start_date.isoformat(),
        end_date_exclusive=end_date_exclusive.isoformat(),
        granularity=granularity,
        metric=metric,
        currency=detected_currency,
        total_cost=total_cost,
        service_totals=sorted_service_totals,
        highest_cost_service=highest_cost_service,
        results_by_time=period_costs,
        raw_results=raw_results,
    )
