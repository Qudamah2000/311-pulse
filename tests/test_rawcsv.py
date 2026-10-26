"""Tests for pulse.rawcsv, using a small fixture with each known export bug."""

from pathlib import Path

import pytest

from pulse import rawcsv

FIXTURE = Path(__file__).parent / "fixtures" / "sr_sample.csv"


@pytest.fixture(scope="module")
def df():
    return rawcsv.read_raw_csv(FIXTURE)


def test_reads_every_row_with_the_expected_columns(df):
    assert len(df) == 8
    assert list(df.columns) == rawcsv.COLUMNS


def test_merges_unquoted_comma_in_division(df):
    assert "Parks, Forestry & Recreation" in set(df["Division"])
    assert "Environment, Climate & Forestry" in set(df["Division"])


def test_merges_unquoted_comma_in_section(df):
    assert "Transfer, Disposal & Operations" in set(df["Section"])


def test_leaves_streets_with_spaces_around_the_comma_alone(df):
    row = df[df["First 3 Chars of Postal Code"] == "Intersection"].iloc[0]
    assert row["Intersection Street 1"] == "C N R "
    assert row["Intersection Street 2"] == " C P R/Ray Ave"
    assert row["Division"] == "Transportation Services"


def test_decodes_windows_1252(df):
    assert "CaféTO Encroachment Complaint" in set(df["Service Request Type"])


def test_blanks_are_null_but_the_text_na_is_kept(df):
    assert df["Intersection Street 1"].isna().sum() == 7
    assert "NA" in set(df["Service Request Type"])


def test_repair_row_merges_around_the_single_comma_space():
    fields = ["d", "s", "p", "", "", "w", "t", "Parks", " Forestry & Recreation", "sec"]
    assert rawcsv.repair_row(fields)[7] == "Parks, Forestry & Recreation"


def test_repair_row_refuses_when_the_split_is_ambiguous():
    fields = ["d", "s", "p", "C N R ", " C P R", "w", "t", "Parks", " Forestry", "sec"]
    with pytest.raises(rawcsv.MalformedRowError):
        rawcsv.repair_row(fields)


def test_repair_row_refuses_rows_with_more_than_one_extra_field():
    with pytest.raises(rawcsv.MalformedRowError):
        rawcsv.repair_row(["x"] * 11)
