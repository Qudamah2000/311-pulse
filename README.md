# 311 Pulse

311 Pulse turns the City of Toronto's 311 service request data into a clean PostgreSQL database and an API for request volume, trends, and status by ward and division.

**Status:** in progress. Milestone 1 (ingest) works against the live API. Transform and load are next.

## The data

- **Source:** [City of Toronto Open Data, 311 Service Requests (Customer Initiated)](https://open.toronto.ca/dataset/311-service-requests-customer-initiated/)
- **Shape:** one ZIP file per year. The current year's file is refreshed monthly.
- **Fields:** creation date and time, location, request type, status (Initiated, In Progress, Canceled, Closed), division, section, and ward.
- **Limit:** there is no closed date, so this project doesn't measure how long requests take to resolve.

## How it works

```
Open Data API  ->  ingest (raw ZIPs)  ->  transform (Pandas)  ->  PostgreSQL  ->  FastAPI
```

Only the first step exists so far. The rest follows the milestones below.

## Milestones

- [x] **1. Ingest.** Download the 2023 to 2026 files. Reruns skip files that haven't changed.
- [ ] **2. Transform and load.** Clean the data with Pandas and load it into a normalized PostgreSQL schema on a monthly schedule, with no duplicate rows.
- [ ] **3. API.** A FastAPI service with endpoints for counts by type and ward, monthly trends, status mix, and search. Runs with Docker Compose.
- [ ] **4. Tests and CI.** pytest plus GitHub Actions on every push, at 80%+ coverage.

## Run it

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

python -m pulse.ingest --years 2023 2024 2025 2026
python -m pulse.profiling   # row counts, nulls and distinct values per year
python -m pytest
```

Downloads land in `data/raw/`, which git ignores.

## Design decisions

- **Downloads are all or nothing.** Each file is written to a `.part` file and renamed only when complete, so an interrupted run never leaves a broken ZIP that looks finished.
- **Reruns are cheap.** A small manifest records each file's last-modified date from the API. Unchanged files are skipped, and the monthly refresh of the current year is picked up automatically.
- **A slow API doesn't end the run.** The city's API can take 90+ seconds to answer, so requests wait up to 3 minutes for a reply (but only 10 seconds to connect) and retry with backoff on timeouts and server errors.
- **The city's CSVs are repaired as they're read.** They're Windows-1252, and commas inside names like "Parks, Forestry & Recreation" aren't quoted, which breaks about 8% of rows. A reader merges those values back together with a rule narrow enough to leave valid rows untouched.
- **Reloads replace a year, not individual rows.** The data has no request ID and contains genuine duplicate requests, so each load swaps out a whole year in one transaction.
- **Tests don't touch the network.** A fake session stands in for the API, so the tests run in under a second and work offline.

More detail on problems and decisions is in [NOTES.md](NOTES.md).
