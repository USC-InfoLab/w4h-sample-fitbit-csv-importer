# AGENTS.md — w4h-sample-fitbit-csv-importer

Paired importer for **w4h-sample-fitbit-csv**. Notebook + CLI + tests.

- API key via `W4H_API_KEY` in local `.env` only — never in git.
- Do not add direct Postgres / `to_sql` paths; use the W4H API.
