"""Read the city's raw yearly 311 CSVs, repairing their known export bugs.

Two problems in the files (details in NOTES.md):

1. They're Windows-1252, not UTF-8 ("CaféTO" breaks UTF-8 decoding).
2. Values with a comma aren't quoted. "Parks, Forestry & Recreation",
   "Environment, Climate & Forestry" and "Transfer, Disposal & Operations"
   split into two fields, so those rows have 10 fields instead of 9. That's
   about 8% of rows, so they can't simply be dropped.

The repair only touches rows with one extra field, and merges the two fields
around the single ", " in the row. Every broken row in 2023 to 2026 has exactly
one. Rows that already have 9 fields are never changed, even if they contain
", ", because some street names legitimately have a space before or after the
comma that separates them ("C N R , C P R/Ray Ave").
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

CSV_ENCODING = "cp1252"

COLUMNS = [
    "Creation Date",
    "Status",
    "First 3 Chars of Postal Code",
    "Intersection Street 1",
    "Intersection Street 2",
    "Ward",
    "Service Request Type",
    "Division",
    "Section",
]


class MalformedRowError(ValueError):
    """A row that the comma repair can't fix safely."""


def repair_row(fields: list[str]) -> list[str]:
    """Merge the field pair split by an unquoted ", " back into one value."""
    if len(fields) != len(COLUMNS) + 1:
        raise MalformedRowError(f"Expected {len(COLUMNS) + 1} fields: {fields}")
    splits = [i for i in range(len(fields) - 1) if fields[i + 1].startswith(" ")]
    if len(splits) != 1:
        raise MalformedRowError(f"Can't tell which comma to merge: {fields}")
    i = splits[0]
    return fields[:i] + [fields[i] + "," + fields[i + 1]] + fields[i + 2 :]


def read_raw_csv(path: Path) -> pd.DataFrame:
    """Read a yearly CSV with every column as text and blanks as nulls.

    Reading as text keeps values exactly as the city wrote them. Only empty
    cells count as null, so a real value like "NA" is not lost. The python
    engine is needed because the C engine can't repair bad rows with a
    callback.
    """
    df = pd.read_csv(
        path,
        dtype=str,
        encoding=CSV_ENCODING,
        keep_default_na=False,
        na_values=[""],
        engine="python",
        on_bad_lines=repair_row,
    )
    if list(df.columns) != COLUMNS:
        raise MalformedRowError(f"Unexpected header in {path}: {list(df.columns)}")
    return df
