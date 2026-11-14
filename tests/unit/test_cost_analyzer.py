"""Unit tests for CostAnalyzer breakdowns, trends, and period comparisons."""

from __future__ import annotations

from decimal import Decimal

from app.analyzer.cost_analyzer import CostAnalyzer


def test_get_service_breakdown(sample_collection_result):
    """Verify service breakdown calculates correct percentages."""
    breakdown = CostAnalyzer.get_service_breakdown(sample_collection_result, top_n=3)

    assert len(breakdown) == 3
    # Top service is EC2
    assert breakdown[0].service_name == "Amazon Elastic Compute Cloud - Compute"
    assert breakdown[0].amount == Decimal("87.50")
    # 87.50 / 121.00 * 100 = 72.31%
    assert breakdown[0].percentage_of_total == Decimal("72.31")

    # Second service is RDS
    assert breakdown[1].service_name == "Amazon Relational Database Service"
    assert breakdown[1].amount == Decimal("22.10")
    # 22.10 / 121.00 * 100 = 18.26%
    assert breakdown[1].percentage_of_total == Decimal("18.26")


def test_get_service_breakdown_zero_cost(sample_collection_result):
    """Verify breakdown handles zero total cost without ZeroDivisionError."""
    zero_result = sample_collection_result.model_copy(
        update={
            "total_cost": Decimal("0.0"),
            "service_totals": {"Amazon S3": Decimal("0.0")},
        }
    )
    breakdown = CostAnalyzer.get_service_breakdown(zero_result)
    assert len(breakdown) == 1
    assert breakdown[0].percentage_of_total == Decimal("0.0")


def test_analyze_daily_trends(sample_collection_result):
    """Verify daily trends calculate day-over-day changes, averages, and spikes."""
    trends = CostAnalyzer.analyze_daily_trends(
        sample_collection_result, spike_multiplier=1.1
    )

    assert len(trends.daily_totals) == 2
    day1 = trends.daily_totals[0]
    day2 = trends.daily_totals[1]

    # Day 1: 53.75
    assert day1.amount == Decimal("53.75")
    assert day1.day_over_day_change_amount is None
    assert day1.day_over_day_change_percentage is None

    # Day 2: 67.25 -> change = 67.25 - 53.75 = 13.50 -> 13.50 / 53.75 * 100 = 25.12%
    assert day2.amount == Decimal("67.25")
    assert day2.day_over_day_change_amount == Decimal("13.50")
    assert day2.day_over_day_change_percentage == Decimal("25.12")

    # Average: (53.75 + 67.25) / 2 = 60.50
    assert trends.average_daily_cost == Decimal("60.50")
    assert trends.highest_spending_day == ("2026-11-02", Decimal("67.25"))

    # Spike threshold: 60.50 * 1.1 = 66.55. Day 2 (67.25) is >= 66.55 -> is_spike = True
    assert day2.is_spike is True
    assert len(trends.spike_days) == 1
    assert trends.spike_days[0].usage_date == "2026-11-02"


def test_compare_periods(sample_collection_result):
    """Verify comparison between two periods calculates differences and
    percentage changes.
    """
    # Current period: 121.00
    # Previous period: 100.00
    previous_period = sample_collection_result.model_copy(
        update={"total_cost": Decimal("100.00")}
    )

    comparison = CostAnalyzer.compare_periods(
        current_result=sample_collection_result,
        previous_result=previous_period,
    )

    assert comparison.current_period_cost == Decimal("121.00")
    assert comparison.previous_period_cost == Decimal("100.00")
    assert comparison.absolute_difference == Decimal("21.00")
    # (21.00 / 100.00) * 100 = 21.00%
    assert comparison.percentage_change == Decimal("21.00")


def test_compare_periods_with_zero_previous_cost(sample_collection_result):
    """Verify comparison handles zero previous period cost gracefully."""
    previous_period = sample_collection_result.model_copy(
        update={"total_cost": Decimal("0.00")}
    )

    comparison = CostAnalyzer.compare_periods(
        current_result=sample_collection_result,
        previous_result=previous_period,
    )

    assert comparison.absolute_difference == Decimal("121.00")
    assert comparison.percentage_change is None
