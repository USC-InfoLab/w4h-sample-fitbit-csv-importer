"""CSV read + chunked API import (no full-table DataFrame load for production paths)."""

import csv
from pathlib import Path
from typing import Iterator

from .client import W4HClient


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


def count_csv_rows(csv_path: Path) -> int:
    """Cheap upfront row count (one pass, no full-file load) for progress reporting."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        return sum(1 for _ in reader)


def import_signal(
    client: W4HClient,
    dataset_id: str,
    signal: dict,
    package_root: Path,
    mode: str = "append",
    csv_path: Path | None = None,
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
    description = signal.get("description", "")
    source_url = signal.get("fitbit_api_url")
    source_name = "Fitbit"

    total_inserted = 0
    total_skipped = 0
    last_physical = None

    # Upfront row count for progress reporting only — a chunked import against
    # the full bundled sample data can legitimately take a long time with no
    # feedback otherwise, which is easy to mistake for a hang. If counting
    # fails for any reason, fall back to unnumbered progress rather than
    # failing the import over a cosmetic feature.
    try:
        total_rows = count_csv_rows(csv_path)
    except OSError:
        total_rows = None

    import_chunk_size = 500
    total_chunks = (
        -(-total_rows // import_chunk_size) if total_rows else None
    )  # ceiling division

    rows_done = 0
    chunk_index = 0
    for chunk in iter_csv_rows(csv_path, chunk_size=import_chunk_size):
        chunk_index += 1
        payload = {
            "signal": slug,
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

        rows_done += len(chunk)
        if total_rows:
            print(
                f"{slug}: chunk {chunk_index}/{total_chunks} "
                f"({rows_done}/{total_rows} rows, inserted={total_inserted} skipped={total_skipped})",
                flush=True,
            )
        else:
            print(
                f"{slug}: chunk {chunk_index} ({rows_done} rows so far, "
                f"inserted={total_inserted} skipped={total_skipped})",
                flush=True,
            )

    return {
        "signal": slug,
        "inserted": total_inserted,
        "skipped": total_skipped,
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
    for signal in manifest.get("signals", []):
        results.append(
            import_signal(client, dataset_id, signal, package_root, mode=mode)
        )
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
