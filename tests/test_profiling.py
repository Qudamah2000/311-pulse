"""Tests for pulse.profiling, run against the fixture CSV."""

from pathlib import Path

import pandas as pd
import pytest

from pulse import profiling
from pulse.rawcsv import read_raw_csv

FIXTURE = Path(__file__).parent / "fixtures" / "sr_sample.csv"


@pytest.fixture(scope="module")
def stats():
    return profiling.profile(read_raw_csv(FIXTURE))


def test_counts_rows_nulls_and_duplicates(stats):
    assert stats["rows"] == 8
    assert stats["nulls"]["Intersection Street 2"] == 7
    assert stats["nulls"]["Ward"] == 0
    assert stats["duplicate_rows"] == 1


def test_lists_distinct_category_values(stats):
    assert stats["distinct"]["Status"]["Unknown"] == 2
    assert stats["distinct"]["Ward"]["Unknown"] == 1


def test_parses_creation_dates(stats):
    assert stats["unparsed_dates"] == 0
    assert stats["first_created"] == pd.Timestamp("2023-01-01 01:56:18")


def test_finds_no_id_column_when_none_exists(stats):
    assert stats["unique_columns"] == []


def test_finds_an_id_column_when_one_exists():
    df = pd.DataFrame({"id": ["1", "2", "3"], "status": ["a", "a", "b"]})
    assert profiling.unique_columns(df) == ["id"]


def test_report_says_when_there_is_no_id(stats):
    report = profiling.format_report(2025, stats)
    assert "Columns usable as a unique ID: none" in report
    assert "| Ward | 0 | 0.0 |" in report


def test_main_reports_missing_years(tmp_path, capsys):
    profiling.main(["--years", "2030", "--raw-dir", str(tmp_path)])
    assert "Run ingest first" in capsys.readouterr().out
