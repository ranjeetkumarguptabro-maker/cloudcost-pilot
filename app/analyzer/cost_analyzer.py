"""Cost analytics, service breakdown, trend analysis, and period comparison."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.aws.cost_explorer import CostCollectionResult
from app.logging_config import get_logger

logger = get_logger(__name__)


class ServiceBreakdownItem(BaseModel):
    """Cost details and proportion for an AWS service."""

    service_name: str
    amount: Decimal
    percentage_of_total: Decimal = Field(
        description="Percentage of the total bill contributed by this service (0-100)"
    )
    currency: str


class DailyTrendEntry(BaseModel):
    """Daily cost entry with day-over-day change."""

    usage_date: str
    amount: Decimal
    currency: str
    day_over_day_change_amount: Decimal | None = None
    day_over_day_change_percentage: Decimal | None = None
    is_spike: bool = False


class DailyTrendAnalysis(BaseModel):
    """Analysis of daily spending trend and anomalies."""

    daily_totals: list[DailyTrendEntry]
    average_daily_cost: Decimal
    highest_spending_day: tuple[str, Decimal] | None = None
    spike_days: list[DailyTrendEntry] = Field(default_factory=list)
    currency: str


class CostComparisonSummary(BaseModel):
    """Comparative analysis between two reporting periods."""

    current_period_cost: Decimal
    previous_period_cost: Decimal
    absolute_difference: Decimal
    percentage_change: Decimal | None
    currency: str
    highest_cost_service: tuple[str, Decimal] | None
    top_services: list[ServiceBreakdownItem]


class CostAnalyzer:
    """Provides analytical operations on collected AWS cost data."""

    @staticmethod
    def get_service_breakdown(
        collection_result: CostCollectionResult,
        top_n: int = 10,
    ) -> list[ServiceBreakdownItem]:
        """Calculate service cost distribution and percentage contribution.

        Args:
            collection_result: Result of Cost Explorer collection.
            top_n: Maximum number of top services to include.

        Returns:
            List of ServiceBreakdownItem sorted descending by cost.
        """
        total = collection_result.total_cost
        items: list[ServiceBreakdownItem] = []

        for service, amount in list(collection_result.service_totals.items())[:top_n]:
            if total > Decimal("0.0"):
                percentage = (amount / total) * Decimal("100.0")
                percentage_rounded = round(percentage, 2)
            else:
                percentage_rounded = Decimal("0.0")

            items.append(
                ServiceBreakdownItem(
                    service_name=service,
                    amount=amount,
                    percentage_of_total=percentage_rounded,
                    currency=collection_result.currency,
                )
            )

        return items

    @staticmethod
    def analyze_daily_trends(
        collection_result: CostCollectionResult,
        spike_multiplier: float = 1.5,
    ) -> DailyTrendAnalysis:
        """Analyze daily spending trajectory, day-over-day changes, and spikes.

        Args:
            collection_result: Daily cost collection result.
            spike_multiplier: Multiplier over daily average to flag as a spike.

        Returns:
            DailyTrendAnalysis containing breakdown and potential spikes.
        """
        if collection_result.granularity != "DAILY":
            logger.warning(
                "analyze_daily_trends called on non-daily granularity: %s",
                collection_result.granularity,
            )

        entries: list[DailyTrendEntry] = []
        previous_amount: Decimal | None = None
        total_amount = Decimal("0.0")

        for period in collection_result.results_by_time:
            amount = period.total_amount
            total_amount += amount

            change_amount: Decimal | None = None
            change_pct: Decimal | None = None

            if previous_amount is not None:
                change_amount = amount - previous_amount
                if previous_amount > Decimal("0.0"):
                    change_pct = round((change_amount / previous_amount) * Decimal("100.0"), 2)

            entries.append(
                DailyTrendEntry(
                    usage_date=period.start_date,
                    amount=amount,
                    currency=period.currency,
                    day_over_day_change_amount=change_amount,
                    day_over_day_change_percentage=change_pct,
                )
            )
            previous_amount = amount

        count = len(entries)
        avg_daily = (total_amount / Decimal(count)) if count > 0 else Decimal("0.0")
        spike_threshold = avg_daily * Decimal(str(spike_multiplier))

        highest_day: tuple[str, Decimal] | None = None
        spike_days: list[DailyTrendEntry] = []

        if entries:
            max_entry = max(entries, key=lambda e: e.amount)
            highest_day = (max_entry.usage_date, max_entry.amount)

            for entry in entries:
                if avg_daily > Decimal("0.0") and entry.amount >= spike_threshold:
                    entry.is_spike = True
                    spike_days.append(entry)

        return DailyTrendAnalysis(
            daily_totals=entries,
            average_daily_cost=round(avg_daily, 2),
            highest_spending_day=highest_day,
            spike_days=spike_days,
            currency=collection_result.currency,
        )

    @staticmethod
    def compare_periods(
        current_result: CostCollectionResult,
        previous_result: CostCollectionResult,
        top_services_count: int = 5,
    ) -> CostComparisonSummary:
        """Compare current period spending with a previous period.

        Args:
            current_result: Current period cost collection.
            previous_result: Previous period cost collection.
            top_services_count: Number of top services to include in summary.

        Returns:
            CostComparisonSummary with absolute and percentage differences.
        """
        current_total = current_result.total_cost
        previous_total = previous_result.total_cost
        diff = current_total - previous_total

        pct_change: Decimal | None = None
        if previous_total > Decimal("0.0"):
            pct_change = round((diff / previous_total) * Decimal("100.0"), 2)

        top_services = CostAnalyzer.get_service_breakdown(
            current_result,
            top_n=top_services_count,
        )

        return CostComparisonSummary(
            current_period_cost=current_total,
            previous_period_cost=previous_total,
            absolute_difference=diff,
            percentage_change=pct_change,
            currency=current_result.currency,
            highest_cost_service=current_result.highest_cost_service,
            top_services=top_services,
        )
