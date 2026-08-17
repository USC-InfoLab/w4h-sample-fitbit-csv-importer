"""Load W4H_API_KEY and related settings from environment / .env (never committed)."""

import os
from pathlib import Path

from dotenv import load_dotenv

_PKG_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PKG_ROOT / ".env")


def require_api_key() -> str:
    key = os.environ.get("W4H_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Set W4H_API_KEY in your environment or .env (copy .env.example). "
            "Generate from W4H Profile → API keys."
        )
    return key


def api_base() -> str:
    return os.environ.get("W4H_API_BASE", "http://localhost:2026").rstrip("/")


def sample_package_path() -> Path:
    raw = os.environ.get("W4H_SAMPLE_FITBIT_CSV_PATH", "../w4h-sample-fitbit-csv").strip()
    p = Path(raw)
    if not p.is_absolute():
        p = (_PKG_ROOT / p).resolve()
    return p


def dataset_id() -> str:
    return os.environ.get("W4H_DATASET_ID", "sample-fitbit-csv").strip()
