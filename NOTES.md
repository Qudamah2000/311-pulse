# Build notes

Problems I hit, decisions I made, and why. These double as interview stories.

| Date | What happened | What I did |
| --- | --- | --- |
| 2026-10-22 | The 311 dataset has no closed date, only a status (Initiated, In Progress, Canceled, Closed). | Dropped resolution-time analytics from the plan. The API will cover volume, trends and status instead. |
| 2026-10-22 | The city refreshes the current year's file every month, so "already downloaded" isn't enough to skip a file. | Ingest keeps a manifest of each file's last-modified date and downloads again when it changes. |
