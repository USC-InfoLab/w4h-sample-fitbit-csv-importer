# AGENTS.md — w4h-sample-fitbit-csv-importer

Importer for the paired **`w4h-sample-fitbit-csv`** package: notebook + CLI + `run.sh` + tests. Human workflow: [README.md](./README.md). The shared W4H architecture overview is at the end of this file.

## Where this repo fits in W4H

- **Layer:** contribution, kinds `notebook` + `cli`, catalog slug `w4h-sample-fitbit-csv-importer`, **`runnable = true`**. It was the first in-app runnable contribution (ADR-022) and is the reference implementation of the `run.sh` contract.
- **It is how the platform's default demo data gets into Postgres.** It is a plain API client; all writes go through `w4h-api`, which enforces ingest ACL and registers mappings.
- **Three ways it runs:**
  1. In-app: **Run import...** → `POST /contributions/w4h-sample-fitbit-csv-importer/run` → `w4h-api` spawns `../w4h-sample-fitbit-csv-importer/run.sh import --mode append|replace` with the user's own `W4H_API_KEY`, `W4H_API_BASE`, `W4H_DATASET_ID`.
  2. By hand: `./run.sh import`, the CLI, or the notebook.
  3. Docker: `w4h-docker`'s `notebooks` image pip-installs this package and preloads `import_fitbit_csv.ipynb`.
- **Downstream:** creates `ds_<dataset_id>.fitbit_{subjects,weight,heart_rate,calories}` and their `w4h.tables` mappings, which `w4h-sql-compute-mets`, `w4h-demo-approximate-queries` and the Analytics tab rely on.

## Data path

```text
../w4h-sample-fitbit-csv/manifest.yaml + data/*.csv
  → manifest.py (load) → vendor_spec.py (report rows that break declared interval/types; still imported)
  → csv_import.py: 500-row chunks → client.py → POST /datasets/:id/import/csv-batch
       payload: signal, table_prefix="fitbit", mode, dedupe_columns, columns, mapping(+sampling_interval),
                description, source_name, source_url, rows
  → stdout: human lines + "@@PROGRESS@@ {json}" lines for the in-app progress bar
```

`mode=replace` only applies to the first chunk of each signal (truncate, then append). Dedupe keys per signal are hard-coded in `csv_import.py` (`id` / `id,date,time` / `id,date,timestamp`).

## Commands

| Command | Purpose |
|---|---|
| `pip install -e ".[dev]"` | Install + pytest (`.[notebook]` adds ipywidgets) |
| `./run.sh import [--mode append\|replace]` | Same entry point as in-app Run; bootstraps `.venv`, prompts for a key only on a TTY |
| `w4h-sample-fitbit-csv-import import --dataset-id <id> --mode replace` | Full load |
| `w4h-sample-fitbit-csv-import sync --dataset-id <id> --signal weight [--file …]` | Append-only, cron-friendly |
| `pytest tests/test_manifest.py tests/test_vendor_spec.py -q` | Offline tests |
| `pytest tests/test_import_api.py -m integration -q` | Needs a running `w4h-api`, `W4H_API_KEY`, `W4H_DATASET_ID` |

Env: `W4H_API_KEY`, `W4H_API_BASE` (default `http://localhost:2026`), `W4H_DATASET_ID` (no default, on purpose), `W4H_SAMPLE_FITBIT_CSV_PATH` (default `../w4h-sample-fitbit-csv`).

## Contracts other repos depend on

| Contract | Who depends on it |
|---|---|
| `run.sh [import\|sync] [args]`, non-interactive when `W4H_API_KEY` is set | `w4h-api/lib/contribution-runner.js` |
| `@@PROGRESS@@ {json}` with `signal`, `signal_index`, `signal_count`, `rows_done`, `rows_total`, `inserted`, `skipped`, `misfits` | Runner → `contribution_runs.progress` → app progress bar |
| `table_prefix: "fitbit"` | Table names `fitbit_*`, which must match tables loaded by `w4h-fitbit-csv-file-importer` and are bound by `w4h-sql-compute-mets` |
| Python package `w4h_sample_fitbit_csv_importer` + `notebook/` | `w4h-docker/notebooks/Dockerfile` copies them |

## Hard boundaries

- API key only in local `.env` or the environment; never in git or notebook outputs.
- No direct Postgres access or `to_sql`; only the W4H API.
- Do not `replace` into read-only **W4H Samples** datasets (the API refuses anyway).
- Vendor-spec misfits are reported, not rejected; keep the documented fixtures in the sample repo detectable.

## Git expectations for agents

- Do not `git commit` or `git push` unless the user asks.
- Manifest-shape changes need coordinated PRs with `w4h-sample-fitbit-csv`; packaging changes may need `w4h-docker`.

<!-- BEGIN w4h-system-overview: identical in every W4H repo's AGENTS.md. Edit all copies together. -->

## W4H system overview (shared across all repos)

**W4H (Wearables for Health) Toolkit** loads wearable-device data into PostgreSQL, organizes it by team, project and dataset, controls access, and runs curated analyses on it. Each signal is a **GeoMTS** (Geospatial Multivariate Time Series) table whose roles (`subject`, `time`, optional `geo`, `values[]`) are stored in `w4h.tables.mapping_json`, not in fixed column names. Three repos form the platform, one packages it, and the rest are **contributions** listed in the in-app catalog (`w4h.contributions`).

| Repo | Role |
|---|---|
| `w4h-api` | Express API and Postgres DDL (`w4h` schema): auth, ACL, ingest, catalog, contribution runner, SQL engine. Port 2026 |
| `w4h-app` | Vue 3 + Vite SPA; talks only to `w4h-api`. Port 5173 |
| `w4h-docs` | Product rules, MVP, ADRs and guides; imported by the API as in-app Help. Owns product decisions |
| `w4h-docker` | Compose stack (`api`, `app`, `notebooks`) built from sibling repos; Postgres is external |
| `w4h-sample-fitbit-csv`, `w4h-sample-icde-demo-csv` | Synthetic sample CSVs plus `manifest.yaml` (ICDE includes a `gps_track` geo signal) |
| `w4h-sample-fitbit-csv-importer`, `w4h-sample-icde-demo-csv-importer` | Runnable importers (notebook, CLI, `run.sh`) for those samples |
| `w4h-fitbit-csv-file-importer` | Runnable importer for user-supplied Fitbit CSVs: profile headers, review a drafted mapping, ingest |
| `w4h-sql-compute-mets` | SQL contribution (YAML + SQL template) that `w4h-api` executes in-process |
| `fft_approximate` | Postgres C extension, catalog slug `fft-approximate`; no API involvement |
| `w4h-demo-approximate-queries` | Notebook comparing `fft_approximate` with exact averages over direct Postgres |

**Main flows:**

1. **Ingest:** importers post 500-row chunks to `POST /datasets/:id/import/csv-batch`. `lib/ingest-csv.js` creates `ds_<dataset_id>.<table_prefix>_<signal>` and upserts its `w4h.tables` mapping.
2. **In-app Run (ADR-022):** `POST /contributions/:slug/run` makes `lib/contribution-runner.js` spawn `../<slug>/run.sh` with the user's `W4H_API_KEY`, `W4H_API_BASE` and `W4H_DATASET_ID`. Stdout lines `@@PROGRESS@@ {json}` drive the progress bar.
3. **SQL analytics (ADR-023):** `lib/sql-contribution-engine.js` reads `../<slug>/manifest.yaml` and `sql/`, binds identifiers from `w4h.tables`, and runs in-process. There is no free-SQL endpoint.
4. **Extensions:** the operator installs `fft_approximate` on their Postgres; notebooks call it directly.

**Layout:** clone every repo as a sibling in one folder. The API finds contributions at `../<slug>` (override `CONTRIBUTION_RUNNER_REPO_ROOT`) and docs at `DOCS_REPO_PATH=../w4h-docs`.

**Cross-repo changes:** `w4h-api` first (regenerate `API_INDEX.md`), then `w4h-app`, then `w4h-docs`. Catalog rows are seeded in `w4h-api/data/schema.sql`. Start at `w4h-docs/dev/mvp.md` and `w4h-docs/dev/ADR-README.md` for decisions, and `w4h-docs/dev/developer-setup.md` for local setup, getting an API key, test personas, troubleshooting, per-repo test commands, default branches and a glossary. Do not commit or push unless asked; never commit `.env` files, API keys or participant data.

<!-- END w4h-system-overview -->
