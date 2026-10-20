"""Minimum-group-size privacy protection for PulseIQ metric outputs."""

import csv
import re
from pathlib import Path


def load_thresholds(csv_path):
    """Load numeric minimum group sizes from the metric dictionary."""
    thresholds = {}
    with Path(csv_path).open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            raw = (row.get("minimum_group_size") or "").strip()
            match = re.match(r"^(\d+)", raw)
            thresholds[row["metric_id"]] = int(match.group(1)) if match else None
    return thresholds


def can_publish(metric_id, employee_count, thresholds):
    """Allow publication only when the configured minimum group size is met."""
    if metric_id not in thresholds:
        raise KeyError(f"Unknown metric: {metric_id}")

    minimum = thresholds[metric_id]
    if minimum is None:
        raise ValueError(
            f"No minimum group size configured for {metric_id}; "
            "confirm its reporting policy before publishing."
        )

    if employee_count < 0:
        raise ValueError("employee_count cannot be negative")

    return employee_count >= minimum
