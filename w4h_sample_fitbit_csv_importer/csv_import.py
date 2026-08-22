"""CSV read + chunked API import (no full-table DataFrame load for production paths)."""

import csv
import json
from pathlib import Path
from typing import Iterator

from .client import W4HClient
from .vendor_spec import MisfitTracker, check_row

# Prefix marking a machine-readable progress line on stdout. w4h-api's runner
# (contribution-runner.js) parses lines with this prefix into the run's
# structured `progress` column instead of just appending them to the raw log —
# large datasets can take a while, and this is what drives the in-app progress bar.
PROGRESS_MARKER = "@@PROGRESS@@"


def _count_csv_rows(csv_path: Path) -> int:
    """Cheap upfront row count (line count, minus header) so progress has a
    denominator. A second pass over the file, but negligible next to the
    per-chunk network round trips that follow."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        return max(sum(1 for _ in f) - 1, 0)


def _dedupe_columns_for_signal(slug: str) -> list[str]:
    if slug == "subjects":
        return ["id"]
    if slug == "weight":
        return ["id", "date", "time"]
    if slug == "heart_rate":
        return ["id", "date", "timestamp"]
    if slug == "calories":
        return ["id", "date", "time"]
    return []


def iter_csv_rows(csv_path: Path, chunk_size: int = 500) -> Iterator[list[dict]]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        chunk: list[dict] = []
        for row in reader:
            chunk.append(dict(row))
            if len(chunk) >= chunk_size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk


def import_signal(
    client: W4HClient,
    dataset_id: str,
    signal: dict,
    package_root: Path,
    mode: str = "append",
    csv_path: Path | None = None,
    signal_index: int = 1,
    signal_count: int = 1,
) -> dict:
    slug = signal["slug"]
    if csv_path is None:
        rel = signal.get("file", "")
        csv_path = (package_root / rel).resolve()
    else:
        csv_path = csv_path.resolve()
    if not csv_path.is_file():
        raise FileNotFoundError(f"Sample CSV missing: {csv_path}")

    columns = signal.get("columns", [])
    mapping = signal.get("geomts_mapping")
    sampling_interval = signal.get("sampling_interval")
    description = signal.get("description", "")
    source_url = signal.get("fitbit_api_url")
    source_name = "Fitbit"

    rows_total = _count_csv_rows(csv_path)
    print(
        f"[{signal_index}/{signal_count}] {slug}: importing {rows_total} row(s) from {csv_path.name}",
        flush=True,
    )

    total_inserted = 0
    total_skipped = 0
    last_physical = None
    misfits = MisfitTracker()

    for chunk in iter_csv_rows(csv_path):
        for row in chunk:
            misfits.record(row, check_row(columns, mapping, sampling_interval, row))

        payload = {
            "signal": slug,
            "table_prefix": "fitbit",
            "mode": mode if total_inserted == 0 and total_skipped == 0 else "append",
            "dedupe_columns": _dedupe_columns_for_signal(slug),
            "columns": columns,
            "mapping": mapping,
            "description": description,
            "source_name": source_name,
            "source_url": source_url,
            "rows": chunk,
        }
        if mode == "replace" and total_inserted == 0 and total_skipped == 0:
            payload["mode"] = "replace"
        result = client.import_csv_batch(dataset_id, payload)
        total_inserted += int(result.get("inserted", 0))
        total_skipped += int(result.get("skipped", 0))
        last_physical = {
            "physical_schema": result.get("physical_schema"),
            "physical_table": result.get("physical_table"),
        }

        rows_done = total_inserted + total_skipped
        pct = int(rows_done * 100 / rows_total) if rows_total else 100
        skipped_note = f", {total_skipped} skipped" if total_skipped else ""
        print(
            f"[{signal_index}/{signal_count}] {slug}: {rows_done}/{rows_total} rows ({pct}%){skipped_note}",
            flush=True,
        )
        print(
            f"{PROGRESS_MARKER} "
            + json.dumps(
                {
                    "signal": slug,
                    "signal_index": signal_index,
                    "signal_count": signal_count,
                    "rows_done": rows_done,
                    "rows_total": rows_total,
                    "inserted": total_inserted,
                    "skipped": total_skipped,
                    "misfits": misfits.total,
                }
            ),
            flush=True,
        )

    if misfits.total:
        print(
            f"[{signal_index}/{signal_count}] {slug}: {misfits.total} vendor-spec misfit(s) "
            f"detected (rows still imported — see detail below)",
            flush=True,
        )
        for entry in misfits.summary():
            print(f"    - {entry['type']} on '{entry['column']}': {entry['count']} row(s)", flush=True)
            for example in entry["examples"]:
                print(f"        e.g. {example}", flush=True)

    return {
        "signal": slug,
        "inserted": total_inserted,
        "skipped": total_skipped,
        "misfits": misfits.total,
        "misfit_detail": misfits.summary(),
        **(last_physical or {}),
    }


def import_all(
    client: W4HClient,
    dataset_id: str,
    manifest: dict,
    package_root: Path,
    mode: str = "replace",
) -> list[dict]:
    results = []
    signals = manifest.get("signals", [])
    signal_count = len(signals)
    print(f"Starting import: {signal_count} signal table(s)", flush=True)
    for signal_index, signal in enumerate(signals, start=1):
        results.append(
            import_signal(
                client,
                dataset_id,
                signal,
                package_root,
                mode=mode,
                signal_index=signal_index,
                signal_count=signal_count,
            )
        )
    print(f"Import complete: {signal_count} signal table(s) processed", flush=True)
    return results


def sync_signal(
    client: W4HClient,
    dataset_id: str,
    signal: dict,
    package_root: Path,
    csv_path: Path | None = None,
) -> dict:
    """Append-only sync for cron — dedupe on natural keys."""
    return import_signal(
        client, dataset_id, signal, package_root, mode="append", csv_path=csv_path
    )
