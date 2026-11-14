"""Unit tests for atomic JSON export utility."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.reports.exporter import export_to_json


def test_export_to_json_success(tmp_path: Path):
    """Verify export_to_json writes valid JSON atomically and cleans up temp files."""
    dest = tmp_path / "output_dir" / "test_cost.json"
    data = {
        "account_id": "123456789012",
        "total_cost": "121.00",
        "services": ["EC2", "S3"],
    }

    saved = export_to_json(data, dest)

    assert saved.exists()
    assert saved.resolve() == dest.resolve()

    with saved.open(encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded == data

    # Verify no temporary files remain in output directory
    temp_files = list(dest.parent.glob(".tmp_*"))
    assert len(temp_files) == 0


def test_export_to_json_unserializable_data(tmp_path: Path):
    """Verify non-serializable objects raise TypeError and do not leave corrupted files."""
    dest = tmp_path / "bad.json"
    data = {"bad_obj": object()}

    with pytest.raises(TypeError):
        export_to_json(data, dest)

    assert not dest.exists()
