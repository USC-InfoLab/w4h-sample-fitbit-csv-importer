# W4H Sample Fitbit CSV Importer

Notebook + CLI to import the paired sample package **[w4h-sample-fitbit-csv](https://github.com/USC-InfoLab/w4h-sample-fitbit-csv)** into W4H. Credentials stay in a local `.env` (never committed).

**Publisher:** usc-infolab · **Kinds:** notebook, CLI · **Language:** Python

Admins adapt this notebook to ingest Fitbit CSV. The same repo includes a CLI for scheduled and incremental updates.

## Who should do what

| Role | What to do |
|------|------------|
| **Admin** | Adapt the notebook for your export shape, then ingest into **your team’s** catalog. Use the CLI (`import` / `sync`) for cron and incremental updates. |
| **User** | Use analysis contributions against loaded datasets. You cannot add datasets or edit raw tables. |
| **Super admin** | May seed/replace canonical **W4H Samples** datasets. Everyone else treats sandbox as read. |

## Prerequisites

- Running **w4h-api** and a personal API key (Profile → API keys)
- Clone this repo **next to** the sample package:

```
W4H/
  w4h-sample-fitbit-csv/
  w4h-sample-fitbit-csv-importer/
```

## Credentials

```bash
cp .env.example .env
# Edit .env — set W4H_API_KEY (and W4H_DATASET_ID)
```

Never commit `.env` or paste keys into notebook outputs.

## Install

```bash
pip install -e ".[dev]"
```

## One-command run (`run.sh`)

```bash
./run.sh import          # or: ./run.sh sync --signal weight --file ...
```

Bootstraps a local `.venv`, installs this package, and runs the CLI. If `W4H_API_KEY` isn't already set in your environment, it prompts for it (and the API base URL) interactively and offers to save both to `.env`. Set `W4H_API_KEY`/`W4H_API_BASE` in the environment beforehand to run it non-interactively — this is the same entrypoint the in-app "Run" trigger uses.

## Notebook (primary)

Open [`notebook/import_fitbit_csv.ipynb`](notebook/import_fitbit_csv.ipynb). It loads `manifest.yaml` from the sample repo, shows GeoMTS mapping, and posts chunked rows to `POST /datasets/:id/import/csv-batch`.

Admins: run the import cells against a dataset you created.  
Users: run through mapping/preview; skip `mode="replace"` on W4H Samples.

## CLI import (admins)

```bash
export W4H_API_KEY=w4h_sk_...   # or use .env
w4h-sample-fitbit-csv-import import --dataset-id sample-fitbit-csv --mode replace
```

## Incremental sync (cron)

```bash
w4h-sample-fitbit-csv-import sync --dataset-id sample-fitbit-csv --signal weight --file /path/to/new_weight.csv
```

Example crontab:

```cron
0 2 * * * cd /path/to/w4h-sample-fitbit-csv-importer && /usr/bin/env $(cat .env | xargs) w4h-sample-fitbit-csv-import sync --dataset-id sample-fitbit-csv --signal weight --file /data/fitbit_weight_delta.csv >> /var/log/w4h-fitbit-sync.log 2>&1
```

Use `sync` without `--file` to re-read the sample package CSV (dedupe skips existing rows).

## Tests

```bash
pytest tests/test_manifest.py -q
```

Optional API tests:

```bash
export W4H_API_KEY=...
export W4H_DATASET_ID=sample-fitbit-csv
pytest tests/test_import_api.py -m integration -q
```

## API

Uses `POST /datasets/:id/import/csv-batch` (no direct database access).
