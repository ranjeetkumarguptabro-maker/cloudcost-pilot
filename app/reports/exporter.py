"""Atomic JSON and data export utilities for CloudCost Pilot."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from app.logging_config import get_logger

logger = get_logger(__name__)


def export_to_json(
    data: dict[str, Any],
    output_path: str | Path,
    indent: int = 2,
) -> Path:
    """Atomically write data dictionary to a JSON file.

    Writes to a temporary file in the target directory and replaces
    the destination atomically using os.replace to prevent partial writes.

    Args:
        data: JSON-serializable dictionary.
        output_path: Destination path for the JSON file.
        indent: Indentation spaces for pretty printing.

    Returns:
        Path of the exported file.

    Raises:
        OSError: If directory creation or write fails.
        TypeError: If data is not JSON serializable.
    """
    target = Path(output_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    # Use a temporary file in the same directory to allow atomic os.replace across filesystem boundaries
    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target.parent,
        prefix=f".tmp_{target.stem}_",
        suffix=".json",
        delete=False,
    )

    try:
        json.dump(data, temp_file, indent=indent, ensure_ascii=False)
        temp_file.flush()
        os.fsync(temp_file.fileno())
        temp_file.close()

        # Atomic rename
        temp_path = Path(temp_file.name)
        temp_path.replace(target)
        logger.info("Successfully exported %d bytes to %s", target.stat().st_size, target)
        return target
    except Exception as exc:
        temp_path = Path(temp_file.name)
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        logger.error("Failed to export JSON to %s: %s", target, exc)
        raise
