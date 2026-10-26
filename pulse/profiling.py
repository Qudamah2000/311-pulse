"""Profile the raw yearly 311 CSVs before designing the schema.

Run it after ingest with:
    python -m pulse.profiling --years 2023 2024 2025 2026

For each year it reports row counts, nulls per column, the distinct values of
status, division and ward, the creation date range, and duplicate rows. It also
checks whether any column could serve as a unique request ID, because the
de-duplication design for the load step depends on the answer.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pulse import config
from pulse.rawcsv import read_raw_csv

# Columns whose distinct values are listed in full in the report.
CATEGORY_COLUMNS = ["Status", "Division", "Ward"]


def csv_path_for(raw_dir: Path, year: int) -> Path:
    """The extracted CSV for a year, e.g. data/raw/2025/SR2025.csv."""
    return raw_dir / str(year) / f"SR{year}.csv"


def unique_columns(df: pd.DataFrame) -> list[str]:
    """Columns with no nulls and no repeated values: candidate request IDs."""
    return [
        col for col in df.columns
        if df[col].notna().all() and df[col].is_unique
    ]


def profile(df: pd.DataFrame) -> dict:
    """Summarize one year's rows."""
    created = pd.to_datetime(df["Creation Date"], format="ISO8601", errors="coerce")
    return {
        "rows": len(df),
        "nulls": df.isna().sum().to_dict(),
        "distinct": {
            col: df[col].value_counts(dropna=False).to_dict()
            for col in CATEGORY_COLUMNS
        },
        "unparsed_dates": int(created.isna().sum()),
        "first_created": created.min(),
        "last_created": created.max(),
        "duplicate_rows": int(df.duplicated().sum()),
        "unique_columns": unique_columns(df),
    }


def format_report(year: int, stats: dict) -> str:
    """Render one year's profile as Markdown."""
    lines = [
        f"## {year}",
        "",
        f"- Rows: {stats['rows']:,}",
        f"- Created: {stats['first_created']} to {stats['last_created']}"
        f" ({stats['unparsed_dates']:,} dates didn't parse)",
        f"- Exact duplicate rows: {stats['duplicate_rows']:,}",
        f"- Columns usable as a unique ID: {', '.join(stats['unique_columns']) or 'none'}",
        "",
        "| Column | Nulls | % |",
        "| --- | --- | --- |",
    ]
    for col, count in stats["nulls"].items():
        share = 100 * count / stats["rows"] if stats["rows"] else 0
        lines.append(f"| {col} | {count:,} | {share:.1f} |")
    for col, counts in stats["distinct"].items():
        lines += ["", f"{col} ({len(counts)} distinct):", ""]
        lines += [f"- {value}: {count:,}" for value, count in counts.items()]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Profile the raw 311 CSVs.")
    parser.add_argument(
        "--years", type=int, nargs="+", default=config.DEFAULT_YEARS,
        help="Years to profile, e.g. --years 2024 2025",
    )
    parser.add_argument(
        "--raw-dir", type=Path, default=config.RAW_DIR,
        help="Folder with the extracted CSVs (default: data/raw)",
    )
    args = parser.parse_args(argv)
    for year in args.years:
        path = csv_path_for(args.raw_dir, year)
        if not path.exists():
            print(f"## {year}\n\nNo file at {path}. Run ingest first.\n")
            continue
        print(format_report(year, profile(read_raw_csv(path))) + "\n")


if __name__ == "__main__":
    main()
