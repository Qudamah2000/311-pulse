# Build notes

Problems I hit, decisions I made, and why. These double as interview stories.

| Date | What happened | What I did |
| --- | --- | --- |
| 2026-10-22 | The 311 dataset has no closed date, only a status (Initiated, In Progress, Canceled, Closed). | Dropped resolution-time analytics from the plan. The API will cover volume, trends and status instead. |
| 2026-10-22 | The city refreshes the current year's file every month, so "already downloaded" isn't enough to skip a file. | Ingest keeps a manifest of each file's last-modified date and downloads again when it changes. |
| 2026-10-25 | The first live run failed with a read timeout. The API connected in 0.15 s but took 90 s to answer `package_show`, longer than the 60 s timeout. | Split the timeout into connect (10 s) and read (180 s), and added retries with backoff on timeouts and 429/5xx replies. The next run worked: 2025 downloaded in about 2.5 minutes. |
| 2026-10-25 | `SR2025.csv` isn't UTF-8. Its only non-ASCII byte is `0xE9` (the é in "CaféTO", 50 times), so it's Windows-1252. Reading it as UTF-8 would crash. | Read the CSVs with `encoding="cp1252"` in the transform step. |
| 2026-10-25 | Status values in the file are "Completed" and "Cancelled", not the "Closed" and "Canceled" the dataset page lists. | Treat the docs as a guide only. Profiling found six real values (below), and the schema uses those. |
| 2026-10-25 | Pandas crashed reading 2023: "Expected 9 fields, saw 10". Division and section names with commas aren't quoted, so "Parks, Forestry & Recreation" splits in two. This affects 136,468 rows (about 8%) across four years, too many to drop. | Wrote `pulse/rawcsv.py`, which repairs only rows with 10 fields by merging at the row's single ", ". It doesn't touch 9-field rows, because 16 valid rows have "C N R , C P R" split across two street columns. A blanket "comma + space" rule would have broken those. Row counts after the repair match the raw line counts exactly. |
| 2026-10-25 | There's no request ID, and 2,501 rows are exact duplicates of another row. They look like real separate requests (for example, three "Cadaver - Wildlife" reports in the same second, in adjacent rows), not export errors. | De-duplicate by year, not by row: each load replaces a whole year in one transaction. Every row's date is in its file's year, so a year is a clean unit. Reruns can't double-count, and real duplicate requests are kept. |
| 2026-10-25 | The city reorganized in 2025. "Parks, Forestry & Recreation" became "Environment, Climate & Forestry" plus "Parks and Recreation". | Keep the division names as published, not merged. Trends across 2024 to 2025 for these divisions need a note in the API docs. |

## Raw file format (2025)

`SR2025.csv`: 75 MB unzipped (7 MB ZIP), about 500,000 rows, Windows-1252, CRLF line endings, header row.

| Column | Example | Notes |
| --- | --- | --- |
| Creation Date | `2025-01-01 00:01:05.0000000` | Timestamp with 7 fractional digits, which Python can't parse directly. |
| Status | `Completed` | |
| First 3 Chars of Postal Code | `M8Y` | The only location field on most rows. |
| Intersection Street 1 | | Often empty. |
| Intersection Street 2 | | Often empty. |
| Ward | `Etobicoke-Lakeshore (03)` | Name and number in one field. Split them in the transform step. |
| Service Request Type | `Injured - Domestic` | |
| Division | `Municipal Licensing & Standards` | |
| Section | `Toronto Animal Services` | |

All four years (2023 to 2026) have the same 9 columns. None is a request ID.

## Profiling (task 2)

Run with `python -m pulse.profiling`. Data as of 2026-10-25.

| Year | Rows | Exact duplicates | Date range |
| --- | --- | --- | --- |
| 2023 | 414,282 | 1,104 | Jan 1 to Dec 31 |
| 2024 | 437,043 | 503 | Jan 1 to Dec 31 |
| 2025 | 500,269 | 689 | Jan 1 to Dec 31 |
| 2026 | 430,607 | 205 | Jan 1 to Sep 30 (refreshed monthly) |
| **Total** | **1,782,201** | **2,501** | |

**Unique ID:** none. No column (or the obvious combinations) is unique, and full-row duplicates exist. That rules out a natural-key upsert, so loading replaces a whole year at a time.

**Nulls:** only the two intersection street columns are often empty (81 to 86%), plus 8 rows in 2026 with no request type. Every other column is always filled, but some use placeholders instead of blanks:

- `Unknown` in Status, Division and Ward (7 to 11 rows per year for ward, up to 10,864 for division in 2024). The transform should turn these into nulls.
- `Intersection` in the postal code column (286,599 rows). It means the location is given as two streets instead. All other values are valid three-character codes (`M` + digit + letter).

**Status (6 values, all years):** Completed, Cancelled, New, In Progress, Closed, Unknown.

**Division (7 per year, 9 overall):** Solid Waste Management Services, Transportation Services, Municipal Licensing & Standards, Toronto Water, 311, Unknown (2023 to 2024 only), Parks, Forestry & Recreation (until 2024), then Environment, Climate & Forestry and Parks and Recreation (from 2025).

**Ward:** the 25 current wards plus `Unknown`, always written as `Name (NN)`.

**Timestamps:** all parse, and all are whole seconds (the 7 decimal places are always zero).
