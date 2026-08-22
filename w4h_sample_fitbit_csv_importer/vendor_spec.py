"""Ingest-time checks of a CSV row against the manifest's declared vendor spec.

Only catches structural mismatches the manifest can be checked against
deterministically: does the value parse as its declared column `type`, and
does an intraday timestamp land on the declared `sampling_interval` grid.
Statistical anomalies (e.g. a weight value that is a valid double precision
but wildly out of range for the subject) are NOT in scope here — those need
to look across a subject's/cohort's other rows and belong in a separate
analysis pass, not a per-row ingest check.
"""

import re

_INT_RE = re.compile(r"^-?\d+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_GRID_SECONDS = {"1sec": 1, "1min": 60, "5min": 300, "15min": 900}

MAX_EXAMPLES_PER_KEY = 3


def _is_valid_type(value: str, col_type: str) -> bool:
    if col_type == "integer":
        return bool(_INT_RE.match(value))
    if col_type == "double precision":
        try:
            float(value)
            return True
        except ValueError:
            return False
    if col_type == "date":
        return bool(_DATE_RE.match(value))
    return True  # text, or a declared type this checker doesn't model


def _time_of_day_column(mapping: dict | None) -> str | None:
    time_spec = (mapping or {}).get("time")
    if isinstance(time_spec, dict) and "combine" in time_spec:
        cols = time_spec["combine"]
        if len(cols) >= 2:
            return cols[-1]
    return None


def _seconds_component(raw: str) -> int | None:
    time_part = raw.split("+")[0].rstrip("Z")
    parts = time_part.split(":")
    if len(parts) < 3:
        return None
    try:
        return int(parts[2])
    except ValueError:
        return None


def check_row(columns: list[dict], mapping: dict | None, sampling_interval: str | None, row: dict) -> list[dict]:
    """Return vendor-spec misfits for one CSV row (empty list if none)."""
    misfits = []

    for col in columns:
        name = col.get("name")
        col_type = col.get("type")
        raw = row.get(name)
        if raw in (None, ""):
            continue  # optional/empty fields are not a misfit
        if not _is_valid_type(raw, col_type):
            misfits.append(
                {
                    "type": "type_mismatch",
                    "column": name,
                    "detail": f"value {raw!r} does not match declared type {col_type!r}",
                }
            )

    interval_seconds = _GRID_SECONDS.get(sampling_interval) if sampling_interval else None
    if interval_seconds and interval_seconds >= 60:
        time_col = _time_of_day_column(mapping)
        raw = row.get(time_col) if time_col else None
        if raw:
            seconds = _seconds_component(raw)
            if seconds is not None and seconds != 0:
                misfits.append(
                    {
                        "type": "tampered_timestamp",
                        "column": time_col,
                        "detail": (
                            f"value {raw!r} has non-zero seconds but signal declares "
                            f"sampling_interval={sampling_interval!r} (expected :00 seconds)"
                        ),
                    }
                )

    return misfits


class MisfitTracker:
    """Accumulates check_row() misfits across a signal's rows for reporting."""

    def __init__(self):
        self._counts: dict[tuple[str, str], int] = {}
        self._examples: dict[tuple[str, str], list[str]] = {}

    def record(self, row: dict, misfits: list[dict]) -> None:
        if not misfits:
            return
        locator = {k: row.get(k) for k in ("id", "date") if row.get(k)}
        for m in misfits:
            key = (m["type"], m["column"])
            self._counts[key] = self._counts.get(key, 0) + 1
            examples = self._examples.setdefault(key, [])
            if len(examples) < MAX_EXAMPLES_PER_KEY:
                examples.append(f"{locator} — {m['detail']}")

    @property
    def total(self) -> int:
        return sum(self._counts.values())

    def summary(self) -> list[dict]:
        return [
            {"type": mtype, "column": column, "count": count, "examples": self._examples[(mtype, column)]}
            for (mtype, column), count in self._counts.items()
        ]
