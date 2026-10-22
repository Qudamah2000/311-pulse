"""Milestone 1: download the yearly 311 ZIP files from Toronto Open Data.

Run it with:
    python -m pulse.ingest --years 2023 2024 2025 2026

What it does:
1. Asks the Open Data API (CKAN) which files the 311 dataset has.
2. Keeps the ZIP files for the years you asked for.
3. Skips any file that hasn't changed since the last run. The city refreshes
   the current year's file every month, so a changed date means download again.
4. Downloads to a temporary ".part" file and renames it when complete, so a
   run that gets interrupted never leaves a half-written ZIP behind.
5. Unzips each file into data/raw/<year>/.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path

import requests

from pulse import config

MANIFEST_NAME = "manifest.json"


def get_package(session: requests.Session) -> dict:
    """Return the dataset's metadata from the CKAN package_show endpoint."""
    url = f"{config.CKAN_BASE_URL}/api/3/action/package_show"
    response = session.get(
        url, params={"id": config.PACKAGE_ID}, timeout=config.REQUEST_TIMEOUT
    )
    response.raise_for_status()
    body = response.json()
    if not body.get("success"):
        raise RuntimeError(f"CKAN returned an error: {body.get('error')}")
    return body["result"]


def yearly_resources(package: dict, years: list[int]) -> list[dict]:
    """Pick out the ZIP file for each requested year.

    Resource names look like "311 Service Requests 2026" or
    "311-service-requests-2019", so the year is read from the name.
    """
    wanted = set(years)
    picked = []
    for resource in package.get("resources", []):
        if str(resource.get("format", "")).upper() != "ZIP":
            continue
        match = re.search(r"(20\d{2})", resource.get("name", ""))
        if not match:
            continue
        year = int(match.group(1))
        if year in wanted:
            picked.append(
                {
                    "year": year,
                    "id": resource["id"],
                    "url": resource["url"],
                    "last_modified": resource.get("last_modified"),
                }
            )
    return sorted(picked, key=lambda r: r["year"])


def load_manifest(raw_dir: Path) -> dict:
    """Read the record of what was downloaded last time (empty on first run)."""
    path = raw_dir / MANIFEST_NAME
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_manifest(raw_dir: Path, manifest: dict) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2))


def zip_path_for(raw_dir: Path, year: int) -> Path:
    return raw_dir / f"311-service-requests-{year}.zip"


def needs_download(resource: dict, manifest: dict, raw_dir: Path) -> bool:
    """True if the file is missing locally or the city has updated it."""
    if not zip_path_for(raw_dir, resource["year"]).exists():
        return True
    previous = manifest.get(str(resource["year"]), {})
    return previous.get("last_modified") != resource["last_modified"]


def download(session: requests.Session, url: str, dest: Path) -> None:
    """Stream a file to disk, writing to dest.part first and renaming at the end."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".part")
    with session.get(url, stream=True, timeout=config.REQUEST_TIMEOUT) as response:
        response.raise_for_status()
        with open(partial, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
    partial.replace(dest)


def extract(zip_path: Path, out_dir: Path) -> list[Path]:
    """Unzip a yearly file and return the paths of the extracted files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(out_dir)
        return [out_dir / name for name in archive.namelist()]


def run(years: list[int], raw_dir: Path = config.RAW_DIR, session=None) -> dict:
    """Download and unzip each requested year. Returns what happened per year."""
    session = session or requests.Session()
    package = get_package(session)
    resources = yearly_resources(package, years)
    manifest = load_manifest(raw_dir)
    summary = {}

    found = {r["year"] for r in resources}
    for year in sorted(set(years) - found):
        summary[year] = "not found in dataset"

    for resource in resources:
        year = resource["year"]
        if not needs_download(resource, manifest, raw_dir):
            summary[year] = "unchanged, skipped"
            continue
        zip_path = zip_path_for(raw_dir, year)
        download(session, resource["url"], zip_path)
        extract(zip_path, raw_dir / str(year))
        manifest[str(year)] = {
            "resource_id": resource["id"],
            "last_modified": resource["last_modified"],
        }
        save_manifest(raw_dir, manifest)
        summary[year] = "downloaded"
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Download Toronto 311 data.")
    parser.add_argument(
        "--years", type=int, nargs="+", default=config.DEFAULT_YEARS,
        help="Years to download, e.g. --years 2024 2025",
    )
    parser.add_argument(
        "--raw-dir", type=Path, default=config.RAW_DIR,
        help="Folder for raw downloads (default: data/raw)",
    )
    args = parser.parse_args(argv)
    for year, outcome in sorted(run(args.years, args.raw_dir).items()):
        print(f"{year}: {outcome}")


if __name__ == "__main__":
    main()
