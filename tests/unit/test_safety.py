"""Safety verification tests for CloudCost Pilot.

Ensures that the codebase does not call destructive AWS API operations,
does not expose credentials in logs, and maintains the strict separation
between actual AWS costs and estimated savings.
"""

from __future__ import annotations

import inspect

import app.aws.client
import app.aws.cost_explorer
from app.logging_config import sanitize_message


def test_no_destructive_aws_methods_defined():
    """Verify no destructive API actions (terminate, delete, stop) exist in AWS modules."""
    prohibited_keywords = [
        "terminate_instances",
        "delete_volume",
        "delete_snapshot",
        "stop_instances",
        "modify_instance",
        "reboot_instances",
    ]

    for module in [app.aws.client, app.aws.cost_explorer]:
        functions = inspect.getmembers(module, inspect.isfunction)
        for name, _ in functions:
            for kw in prohibited_keywords:
                assert kw not in name.lower(), f"Prohibited destructive action '{kw}' found in {name}"


def test_log_sanitization_redacts_credentials():
    """Verify sensitive tokens and keys are sanitized from log messages."""
    sensitive_msg = "Error connecting with aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    sanitized = sanitize_message(sensitive_msg)
    assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in sanitized
    assert "REDACTED" in sanitized


def test_actual_costs_not_labeled_as_estimated_savings(sample_collection_result):
    """Verify CostCollectionResult strictly tracks actual costs without mixing estimated savings."""
    export_dict = sample_collection_result.to_export_dict()

    # The billing export must clearly identify actual recorded metrics and not present them as savings
    assert "total_cost" in export_dict
    assert "metric" in export_dict
    assert export_dict["metric"] == "UnblendedCost"
    assert "estimated_savings" not in export_dict
