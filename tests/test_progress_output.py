from pathlib import Path

from w4h_sample_fitbit_csv_importer.csv_import import count_csv_rows, import_signal


class FakeClient:
    """Stub W4HClient — records payloads, returns a canned result per chunk."""

    def __init__(self):
        self.calls = []

    def import_csv_batch(self, dataset_id, payload):
        self.calls.append((dataset_id, payload))
        rows = payload["rows"]
        return {
            "inserted": len(rows),
            "skipped": 0,
            "physical_schema": "ds_test",
            "physical_table": "fitbit_subjects",
        }


def _write_csv(path: Path, n_rows: int):
    lines = ["id,start_date,end_date"]
    for i in range(n_rows):
        lines.append(f"subj-{i},2020-01-01,2020-01-02")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_count_csv_rows(tmp_path):
    csv_path = tmp_path / "subjects.csv"
    _write_csv(csv_path, 7)
    assert count_csv_rows(csv_path) == 7


def test_import_signal_prints_progress_with_totals(tmp_path, capsys):
    csv_path = tmp_path / "subjects.csv"
    _write_csv(csv_path, 3)
    client = FakeClient()
    signal = {"slug": "subjects", "file": "subjects.csv", "columns": []}

    result = import_signal(client, "ds1", signal, tmp_path, mode="replace")

    assert result["inserted"] == 3
    assert len(client.calls) == 1

    out = capsys.readouterr().out
    assert "subjects: chunk 1/1 (3/3 rows, inserted=3 skipped=0)" in out


def test_import_signal_falls_back_when_count_fails(tmp_path, capsys, monkeypatch):
    csv_path = tmp_path / "subjects.csv"
    _write_csv(csv_path, 2)
    client = FakeClient()
    signal = {"slug": "subjects", "file": "subjects.csv", "columns": []}

    def _raise(_path):
        raise OSError("simulated failure reading the file for counting")

    monkeypatch.setattr(
        "w4h_sample_fitbit_csv_importer.csv_import.count_csv_rows", _raise
    )

    # Counting fails, but the import itself must still complete —
    # progress falls back to an unnumbered "so far" format instead of
    # aborting the import over a cosmetic feature.
    result = import_signal(client, "ds1", signal, tmp_path, mode="replace")

    assert result["inserted"] == 2
    out = capsys.readouterr().out
    assert "chunk 1 (2 rows so far, inserted=2 skipped=0)" in out
    assert "chunk 1/1" not in out
