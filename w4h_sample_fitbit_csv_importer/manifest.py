"""Load vendor manifest from w4h-sample-fitbit-csv."""

from pathlib import Path

import yaml


def load_manifest(package_root: Path) -> dict:
    path = package_root / "manifest.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"manifest.yaml not found at {path}")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def signal_by_slug(manifest: dict, slug: str) -> dict:
    for sig in manifest.get("signals", []):
        if sig.get("slug") == slug:
            return sig
    raise KeyError(f"Unknown signal slug: {slug}")
