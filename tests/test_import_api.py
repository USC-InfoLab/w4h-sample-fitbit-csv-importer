import os

import pytest

from w4h_sample_fitbit_csv_importer.client import W4HClient


@pytest.mark.integration
def test_import_subjects_batch():
    if not os.environ.get("W4H_API_KEY", "").strip():
        pytest.skip("W4H_API_KEY not set")
    dataset_id = os.environ.get("W4H_DATASET_ID", "sample-fitbit-csv")
    client = W4HClient()
    result = client.import_csv_batch(
        dataset_id,
        {
            "signal": "subjects",
            "mode": "append",
            "dedupe_columns": ["id"],
            "columns": [
                {"name": "id", "type": "text"},
                {"name": "start_date", "type": "date"},
                {"name": "end_date", "type": "date"},
            ],
            "rows": [{"id": "test-subj", "start_date": "2020-01-01", "end_date": "2020-01-02"}],
            "source_name": "Fitbit",
            "description": "integration test row",
        },
    )
    assert result.get("success") is True
