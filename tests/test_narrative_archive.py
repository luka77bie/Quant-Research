from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from narrative_regime.narrative.archive import (
    NarrativeArchive,
    audit_archive,
    coverage_summary,
    validate_catalog,
)


def _sources() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_id": "central_bank",
                "publisher": "Central Bank",
                "allowed_domain": "central.example",
                "document_type": "pdf",
                "availability_delay_hours": "24",
                "revision_policy": "versioned_official_pdf",
            }
        ]
    )


def _catalog(snapshot: str = "", snapshot_sha256: str = "") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "record_id": "report_2020_q4",
                "source_id": "central_bank",
                "title": "Quarterly report",
                "period_end": "2020-12-31",
                "published_at": "2021-02-08T22:20:39+08:00",
                "publication_time_precision": "second",
                "index_url": "https://central.example/reports/2020-q4",
                "document_url": "https://central.example/files/2020-q4.pdf",
                "expected_document_sha256": hashlib.sha256(
                    FakeResponse.content
                ).hexdigest(),
                "availability_evidence": "official_timestamped_index",
                "historical_snapshot_url": snapshot,
                "historical_snapshot_sha256": snapshot_sha256,
            }
        ]
    )


class FakeResponse:
    content = b"%PDF-1.4\nfixture"

    def raise_for_status(self) -> None:
        return None


class FakeSession:
    def __init__(self, content: bytes | None = None) -> None:
        self.calls = 0
        self.content = content

    def get(self, url: str, timeout: float) -> FakeResponse:
        self.calls += 1
        response = FakeResponse()
        if self.content is not None:
            response.content = self.content
        return response


def test_catalog_derives_conservative_available_at() -> None:
    result = validate_catalog(_catalog(), _sources())

    assert result.loc[0, "published_at"] == pd.Timestamp("2021-02-08 14:20:39Z")
    assert result.loc[0, "available_at"] == pd.Timestamp("2021-02-09 14:20:39Z")


def test_catalog_rejects_unapproved_document_domain() -> None:
    catalog = _catalog()
    catalog.loc[0, "document_url"] = "https://mirror.example/report.pdf"

    with pytest.raises(ValueError, match="domain is not allowed"):
        validate_catalog(catalog, _sources())


def test_catalog_rejects_duplicate_document_urls() -> None:
    catalog = pd.concat([_catalog(), _catalog()], ignore_index=True)
    catalog.loc[1, "record_id"] = "another_report"

    with pytest.raises(ValueError, match="duplicate document_url"):
        validate_catalog(catalog, _sources())


def test_catalog_rejects_duplicate_source_periods() -> None:
    catalog = pd.concat([_catalog(), _catalog()], ignore_index=True)
    catalog.loc[1, "record_id"] = "another_report"
    catalog.loc[1, "document_url"] = "https://central.example/files/other.pdf"

    with pytest.raises(ValueError, match="duplicate source-period"):
        validate_catalog(catalog, _sources())


def test_fetch_writes_pdf_and_provenance_metadata(tmp_path: Path) -> None:
    session = FakeSession()
    archive = NarrativeArchive(tmp_path, session=session, sleep=lambda _: None)

    result = archive.fetch_catalog(_catalog(), _sources())

    assert result.loc[0, "status"] == "downloaded"
    cache_path = Path(result.loc[0, "cache_path"])
    assert cache_path.read_bytes().startswith(b"%PDF-")
    metadata = json.loads(cache_path.with_suffix(".meta.json").read_text())
    assert metadata["document_url"] == _catalog().loc[0, "document_url"]
    assert metadata["retrieved_at"]
    assert metadata["sha256"] == result.loc[0, "sha256"]


def test_valid_cache_avoids_second_request(tmp_path: Path) -> None:
    session = FakeSession()
    archive = NarrativeArchive(tmp_path, session=session, sleep=lambda _: None)

    first = archive.fetch_catalog(_catalog(), _sources())
    second = archive.fetch_catalog(_catalog(), _sources())

    assert first.loc[0, "status"] == "downloaded"
    assert second.loc[0, "status"] == "cached"
    assert session.calls == 1


def test_non_pdf_response_remains_visible_failure(tmp_path: Path) -> None:
    archive = NarrativeArchive(
        tmp_path,
        attempts=2,
        base_delay_seconds=0,
        session=FakeSession(b"<html>queued</html>"),
        sleep=lambda _: None,
    )

    result = archive.fetch_catalog(_catalog(), _sources())

    assert result.loc[0, "status"] == "failed"
    assert "not a PDF" in result.loc[0, "error"]


def test_audit_detects_checksum_change(tmp_path: Path) -> None:
    archive = NarrativeArchive(tmp_path, session=FakeSession(), sleep=lambda _: None)
    result = archive.fetch_catalog(_catalog(), _sources())
    Path(result.loc[0, "cache_path"]).write_bytes(b"%PDF-1.4\nchanged")

    audit = audit_archive(tmp_path, _catalog(), _sources())

    assert audit.loc[0, "archive_status"] == "blocked"
    assert "checksum mismatch" in audit.loc[0, "issues"]


def test_current_official_pdf_without_historical_snapshot_is_provisional(
    tmp_path: Path,
) -> None:
    archive = NarrativeArchive(tmp_path, session=FakeSession(), sleep=lambda _: None)
    archive.fetch_catalog(_catalog(), _sources())

    audit = audit_archive(tmp_path, _catalog(), _sources())

    assert audit.loc[0, "archive_status"] == "ready"
    assert audit.loc[0, "point_in_time_status"] == "provisional"


def test_historical_snapshot_can_verify_point_in_time_record(tmp_path: Path) -> None:
    archive = NarrativeArchive(tmp_path, session=FakeSession(), sleep=lambda _: None)
    first = archive.fetch_catalog(_catalog(), _sources())
    catalog = _catalog(
        "https://web.archive.org/example", str(first.loc[0, "sha256"])
    )
    archive.fetch_catalog(catalog, _sources())

    audit = audit_archive(tmp_path, catalog, _sources())

    assert audit.loc[0, "point_in_time_status"] == "verified"


def test_coverage_gate_blocks_missing_quarters_and_provisional_records(
    tmp_path: Path,
) -> None:
    archive = NarrativeArchive(tmp_path, session=FakeSession(), sleep=lambda _: None)
    archive.fetch_catalog(_catalog(), _sources())
    audit = audit_archive(tmp_path, _catalog(), _sources())

    summary = coverage_summary(audit, start="2020-03-31", end="2020-12-31")

    assert summary["expected_records"] == 4
    assert summary["ready_records"] == 1
    assert summary["coverage_ratio"] == pytest.approx(0.25)
    assert summary["modeling_gate"] == "blocked"
