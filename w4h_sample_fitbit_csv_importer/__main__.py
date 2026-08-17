"""CLI entry: w4h-sample-fitbit-csv-import"""

import argparse
import sys

from .client import W4HClient
from .config import dataset_id, sample_package_path
from .csv_import import import_all, sync_signal
from .manifest import load_manifest, signal_by_slug


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import Fitbit CSV sample data into W4H (API key from .env)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser("import", help="Initial load from sample package")
    p_import.add_argument(
        "--dataset-id",
        default=dataset_id(),
        help="Target w4h.datasets catalog id",
    )
    p_import.add_argument(
        "--mode",
        choices=["replace", "append"],
        default="replace",
        help="replace truncates signal tables on first batch per signal",
    )

    p_sync = sub.add_parser("sync", help="Append new rows (cron-friendly)")
    p_sync.add_argument("--dataset-id", default=dataset_id())
    p_sync.add_argument("--signal", required=True, help="Signal slug, e.g. weight")
    p_sync.add_argument(
        "--file",
        help="Optional CSV path (default: manifest file for signal)",
    )

    args = parser.parse_args(argv)
    package_root = sample_package_path()
    manifest = load_manifest(package_root)
    client = W4HClient()

    if args.command == "import":
        results = import_all(client, args.dataset_id, manifest, package_root, mode=args.mode)
        for r in results:
            print(
                f"{r['signal']}: inserted={r['inserted']} skipped={r['skipped']} "
                f"→ {r.get('physical_schema')}.{r.get('physical_table')}"
            )
        return 0

    if args.command == "sync":
        signal = signal_by_slug(manifest, args.signal)
        csv_path = None
        if args.file:
            from pathlib import Path

            csv_path = Path(args.file).resolve()
        result = sync_signal(client, args.dataset_id, signal, package_root, csv_path=csv_path)
        print(
            f"sync {result['signal']}: inserted={result['inserted']} skipped={result['skipped']}"
        )
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
