"""Tests for pulse.ingest. They use a fake session, so no network is needed."""

import io
import json
import zipfile

import pytest

from pulse import ingest


def make_zip_bytes(filename: str, text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(filename, text)
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, json_body=None, content=b""):
        self._json = json_body
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return self._json

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i : i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeSession:
    """Answers package_show with fixed metadata and serves ZIP bytes by URL."""

    def __init__(self, package, files):
        self.package = package
        self.files = files
        self.downloaded = []

    def get(self, url, params=None, stream=False, timeout=None):
        if url.endswith("/package_show"):
            return FakeResponse(json_body={"success": True, "result": self.package})
        self.downloaded.append(url)
        return FakeResponse(content=self.files[url])


PACKAGE = {
    "resources": [
        {"id": "r26", "name": "311 Service Requests 2026", "format": "ZIP",
         "url": "https://example.test/2026.zip", "last_modified": "2026-10-08T20:00:18"},
        {"id": "r25", "name": "311 Service Requests 2025", "format": "ZIP",
         "url": "https://example.test/2025.zip", "last_modified": "2026-01-08T21:00:18"},
        {"id": "r19", "name": "311-service-requests-2019", "format": "ZIP",
         "url": "https://example.test/2019.zip", "last_modified": "2019-07-23T16:30:13"},
        {"id": "readme", "name": "311-service-requests-readme", "format": "XLSX",
         "url": "https://example.test/readme.xlsx", "last_modified": "2019-07-23T16:30:17"},
    ]
}


def test_yearly_resources_keeps_only_requested_zip_years():
    picked = ingest.yearly_resources(PACKAGE, [2025, 2026])
    assert [r["year"] for r in picked] == [2025, 2026]
    assert all(r["url"].endswith(".zip") for r in picked)


def test_yearly_resources_reads_year_from_either_name_style():
    picked = ingest.yearly_resources(PACKAGE, [2019])
    assert picked[0]["id"] == "r19"


def test_needs_download_when_file_missing(tmp_path):
    resource = ingest.yearly_resources(PACKAGE, [2025])[0]
    assert ingest.needs_download(resource, {}, tmp_path)


def test_skips_when_file_exists_and_unchanged(tmp_path):
    resource = ingest.yearly_resources(PACKAGE, [2025])[0]
    ingest.zip_path_for(tmp_path, 2025).write_bytes(b"zip")
    manifest = {"2025": {"last_modified": resource["last_modified"]}}
    assert not ingest.needs_download(resource, manifest, tmp_path)


def test_downloads_again_when_city_updates_the_file(tmp_path):
    resource = ingest.yearly_resources(PACKAGE, [2026])[0]
    ingest.zip_path_for(tmp_path, 2026).write_bytes(b"old zip")
    manifest = {"2026": {"last_modified": "2026-09-08T20:00:18"}}
    assert ingest.needs_download(resource, manifest, tmp_path)


def test_download_leaves_no_part_file(tmp_path):
    session = FakeSession(PACKAGE, {"https://example.test/2025.zip": b"x" * 5000})
    dest = tmp_path / "out.zip"
    ingest.download(session, "https://example.test/2025.zip", dest)
    assert dest.read_bytes() == b"x" * 5000
    assert not (tmp_path / "out.zip.part").exists()


def test_run_downloads_extracts_then_skips_on_rerun(tmp_path):
    files = {
        "https://example.test/2025.zip": make_zip_bytes("SR2025.csv", "a,b\n1,2\n"),
        "https://example.test/2026.zip": make_zip_bytes("SR2026.csv", "a,b\n3,4\n"),
    }
    session = FakeSession(PACKAGE, files)

    first = ingest.run([2025, 2026], raw_dir=tmp_path, session=session)
    assert first == {2025: "downloaded", 2026: "downloaded"}
    assert (tmp_path / "2025" / "SR2025.csv").read_text() == "a,b\n1,2\n"
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["2026"]["resource_id"] == "r26"

    second = ingest.run([2025, 2026], raw_dir=tmp_path, session=session)
    assert second == {2025: "unchanged, skipped", 2026: "unchanged, skipped"}
    assert len(session.downloaded) == 2


def test_run_reports_years_the_dataset_does_not_have(tmp_path):
    session = FakeSession(PACKAGE, {})
    assert ingest.run([2030], raw_dir=tmp_path, session=session) == {
        2030: "not found in dataset"
    }


def test_make_session_retries_server_errors_on_https():
    retry = ingest.make_session().get_adapter("https://example.test").max_retries
    assert retry.total == ingest.config.REQUEST_RETRIES
    assert 503 in retry.status_forcelist
    assert retry.is_retry("GET", 503)


def test_get_package_raises_when_ckan_reports_failure():
    class FailingSession:
        def get(self, *args, **kwargs):
            return FakeResponse(json_body={"success": False, "error": "nope"})

    with pytest.raises(RuntimeError):
        ingest.get_package(FailingSession())
