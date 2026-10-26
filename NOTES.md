# Build notes

Problems I hit, decisions I made, and why. These double as interview stories.

| Date | What happened | What I did |
| --- | --- | --- |
| 2026-10-22 | The 311 dataset has no closed date, only a status (Initiated, In Progress, Canceled, Closed). | Dropped resolution-time analytics from the plan. The API will cover volume, trends and status instead. |
| 2026-10-22 | The city refreshes the current year's file every month, so "already downloaded" isn't enough to skip a file. | Ingest keeps a manifest of each file's last-modified date and downloads again when it changes. |
| 2026-10-25 | The first live run failed with a read timeout. The API connected in 0.15 s but took 90 s to answer `package_show`, longer than the 60 s timeout. | Split the timeout into connect (10 s) and read (180 s), and added retries with backoff on timeouts and 429/5xx replies. The next run worked: 2025 downloaded in about 2.5 minutes. |
| 2026-10-25 | `SR2025.csv` isn't UTF-8. Its only non-ASCII byte is `0xE9` (the é in "CaféTO", 50 times), so it's Windows-1252. Reading it as UTF-8 would crash. | Read the CSVs with `encoding="cp1252"` in the transform step. |
| 2026-10-25 | Status values in the file are "Completed" and "Cancelled", not the "Closed" and "Canceled" the dataset page lists. | Treat the docs as a guide only. Profiling (task 2) will list the real values, and the transform will map to them. |

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

There's no request ID column, which matters for de-duplication. Task 2 will confirm this across years.
