from pathlib import Path

import pytest

from w4h_sample_fitbit_csv_importer.config import sample_package_path
from w4h_sample_fitbit_csv_importer.manifest import load_manifest, signal_by_slug


@pytest.fixture
def package_root():
    return sample_package_path()


def test_manifest_loads(package_root):
    if not (package_root / "manifest.yaml").is_file():
        pytest.skip("w4h-sample-fitbit-csv not checked out beside importer")
    manifest = load_manifest(package_root)
    assert manifest["vendor"] == "fitbit"
    assert len(manifest["signals"]) >= 2


def test_signal_slugs(package_root):
    if not (package_root / "manifest.yaml").is_file():
        pytest.skip("w4h-sample-fitbit-csv not checked out beside importer")
    manifest = load_manifest(package_root)
    subjects = signal_by_slug(manifest, "subjects")
    assert subjects["file"].endswith("fitbit_subjects.csv")
