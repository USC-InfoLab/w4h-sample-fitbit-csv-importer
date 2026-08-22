import pytest

from w4h_sample_fitbit_csv_importer.config import sample_package_path
from w4h_sample_fitbit_csv_importer.csv_import import iter_csv_rows
from w4h_sample_fitbit_csv_importer.manifest import load_manifest, signal_by_slug
from w4h_sample_fitbit_csv_importer.vendor_spec import MisfitTracker, check_row


def test_type_mismatch_detected():
    columns = [{"name": "value", "type": "integer"}]
    misfits = check_row(columns, None, None, {"value": "not-an-int"})
    assert misfits == [
        {
            "type": "type_mismatch",
            "column": "value",
            "detail": "value 'not-an-int' does not match declared type 'integer'",
        }
    ]


def test_valid_values_produce_no_misfits():
    columns = [{"name": "value", "type": "double precision"}, {"name": "fat_percent", "type": "double precision"}]
    # Empty optional field + a syntactically valid (if wildly out-of-range) value.
    assert check_row(columns, None, None, {"value": "7.6", "fat_percent": ""}) == []


def test_off_grid_timestamp_detected():
    mapping = {"time": {"combine": ["date", "timestamp"]}}
    misfits = check_row([], mapping, "1min", {"timestamp": "15:06:37"})
    assert misfits == [
        {
            "type": "tampered_timestamp",
            "column": "timestamp",
            "detail": (
                "value '15:06:37' has non-zero seconds but signal declares "
                "sampling_interval='1min' (expected :00 seconds)"
            ),
        }
    ]


def test_on_grid_timestamp_not_flagged():
    mapping = {"time": {"combine": ["date", "timestamp"]}}
    assert check_row([], mapping, "1min", {"timestamp": "15:06:00"}) == []


def test_misfit_tracker_bounds_examples():
    tracker = MisfitTracker()
    for i in range(5):
        tracker.record(
            {"id": f"subj-{i}"},
            [{"type": "tampered_timestamp", "column": "timestamp", "detail": "off grid"}],
        )
    assert tracker.total == 5
    [entry] = tracker.summary()
    assert entry["count"] == 5
    assert len(entry["examples"]) == 3  # MAX_EXAMPLES_PER_KEY


def _package_root():
    return sample_package_path()


def test_catches_known_heart_rate_timestamp_fixture():
    package_root = _package_root()
    if not (package_root / "manifest.yaml").is_file():
        pytest.skip("w4h-sample-fitbit-csv not checked out beside importer")

    manifest = load_manifest(package_root)
    signal = signal_by_slug(manifest, "heart_rate")
    csv_path = package_root / signal["file"]
    columns = signal["columns"]
    mapping = signal["geomts_mapping"]
    sampling_interval = signal.get("sampling_interval")

    tracker = MisfitTracker()
    for chunk in iter_csv_rows(csv_path):
        for row in chunk:
            tracker.record(row, check_row(columns, mapping, sampling_interval, row))

    kinds = {entry["type"] for entry in tracker.summary()}
    assert "tampered_timestamp" in kinds
    assert "type_mismatch" not in kinds  # heart_rate values are all well-typed


def test_does_not_catch_known_weight_outlier():
    """The weight outlier (7.6 kg / bmi 2.48) is a statistical anomaly, not a
    structural one — it parses fine as `double precision`, so ingest-time
    vendor-spec checking must NOT flag it. Catching it needs cohort-level
    analysis, not a per-row check."""
    package_root = _package_root()
    if not (package_root / "manifest.yaml").is_file():
        pytest.skip("w4h-sample-fitbit-csv not checked out beside importer")

    manifest = load_manifest(package_root)
    signal = signal_by_slug(manifest, "weight")
    csv_path = package_root / signal["file"]
    columns = signal["columns"]
    mapping = signal["geomts_mapping"]
    sampling_interval = signal.get("sampling_interval")

    tracker = MisfitTracker()
    for chunk in iter_csv_rows(csv_path):
        for row in chunk:
            tracker.record(row, check_row(columns, mapping, sampling_interval, row))

    assert tracker.total == 0
