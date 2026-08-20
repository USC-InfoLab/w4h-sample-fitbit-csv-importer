import pytest

from w4h_sample_fitbit_csv_importer.config import sample_package_path
from w4h_sample_fitbit_csv_importer.csv_import import _dedupe_columns_for_signal
from w4h_sample_fitbit_csv_importer.manifest import load_manifest, signal_by_slug


@pytest.fixture
def package_root():
    return sample_package_path()


def test_manifest_loads(package_root):
    if not (package_root / "manifest.yaml").is_file():
        pytest.skip("w4h-sample-fitbit-csv not checked out beside importer")
    manifest = load_manifest(package_root)
    assert manifest["vendor"] == "fitbit"
    assert len(manifest["signals"]) == 4


def test_signal_slugs(package_root):
    if not (package_root / "manifest.yaml").is_file():
        pytest.skip("w4h-sample-fitbit-csv not checked out beside importer")
    manifest = load_manifest(package_root)
    slugs = [s["slug"] for s in manifest["signals"]]
    assert slugs == ["subjects", "weight", "heart_rate", "calories"]
    for slug in slugs:
        signal = signal_by_slug(manifest, slug)
        csv_path = package_root / signal["file"]
        assert csv_path.is_file(), f"missing {csv_path}"


def test_dedupe_columns_for_four_signals():
    assert _dedupe_columns_for_signal("subjects") == ["id"]
    assert _dedupe_columns_for_signal("weight") == ["id", "date", "time"]
    assert _dedupe_columns_for_signal("heart_rate") == ["id", "date", "timestamp"]
    assert _dedupe_columns_for_signal("calories") == ["id", "date", "time"]
    assert _dedupe_columns_for_signal("unknown") == []
