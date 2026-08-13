from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from narrative_regime.macro.archive import (
    MacroEvidenceArchive,
    audit_macro_evidence,
    extract_visible_text,
)

HTML = """<!doctype html><html><head><meta charset="utf-8"></head>
<body><p>2024-10-31 09:30</p><p>PMI 为 50.1%</p></body></html>""".encode()


class FakeResponse:
    content = HTML

    def raise_for_status(self) -> None:
        return None


class FakeSession:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, url: str, timeout: float, headers: dict[str, str]) -> FakeResponse:
        self.calls += 1
        return FakeResponse()


def _catalog() -> pd.DataFrame:
    return pd.DataFrame(
        [{
            "record_id": "pmi_2024_10",
            "dimension": "growth",
            "period": "2024-10",
            "release_at": "2024-10-31T09:30:00+08:00",
            "source_url": "https://www.stats.gov.cn/release.html",
            "strict_point_in_time_status": "provisional_no_snapshot",
        }]
    )


def _evidence(checksum: str = "") -> pd.DataFrame:
    return pd.DataFrame(
        [{
            "record_id": "pmi_2024_10",
            "expected_page_sha256": checksum,
            "release_evidence_text": "2024-10-31 09:30",
            "release_evidence_precision": "minute",
            "value_evidence_text": "PMI为50.1%",
        }]
    )


def test_fetch_caches_html_and_avoids_second_request(tmp_path: Path) -> None:
    session = FakeSession()
    archive = MacroEvidenceArchive(tmp_path, session=session, sleep=lambda _: None)

    first = archive.fetch_catalog(_catalog(), _evidence())
    second = archive.fetch_catalog(_catalog(), _evidence())

    assert first.loc[0, "status"] == "downloaded"
    assert second.loc[0, "status"] == "cached"
    assert session.calls == 1
    metadata = json.loads(
        Path(first.loc[0, "cache_path"])
        .with_suffix(".meta.json")
        .read_text(encoding="utf-8")
    )
    assert metadata["sha256"] == hashlib.sha256(HTML).hexdigest()


def test_audit_requires_locked_checksum(tmp_path: Path) -> None:
    archive = MacroEvidenceArchive(
        tmp_path, session=FakeSession(), sleep=lambda _: None
    )
    archive.fetch_catalog(_catalog(), _evidence())

    audit, summary = audit_macro_evidence(tmp_path, _catalog(), _evidence())

    assert audit.loc[0, "current_page_status"] == "blocked"
    assert "checksum is not locked" in audit.loc[0, "issues"]
    assert summary["macro_evidence_gate"] == "blocked"


def test_audit_verifies_locked_page_evidence(tmp_path: Path) -> None:
    archive = MacroEvidenceArchive(
        tmp_path, session=FakeSession(), sleep=lambda _: None
    )
    archive.fetch_catalog(_catalog(), _evidence())
    evidence = _evidence(hashlib.sha256(HTML).hexdigest())

    audit, summary = audit_macro_evidence(tmp_path, _catalog(), evidence)

    assert audit.loc[0, "current_page_status"] == "ready"
    assert bool(audit.loc[0, "release_evidence_verified"])
    assert bool(audit.loc[0, "value_evidence_verified"])
    assert summary["macro_evidence_gate"] == "pass_current_page_evidence_only"


def test_audit_detects_page_change(tmp_path: Path) -> None:
    archive = MacroEvidenceArchive(
        tmp_path, session=FakeSession(), sleep=lambda _: None
    )
    result = archive.fetch_catalog(_catalog(), _evidence())
    Path(result.loc[0, "cache_path"]).write_bytes(HTML + b"changed")

    audit, _ = audit_macro_evidence(
        tmp_path, _catalog(), _evidence(hashlib.sha256(HTML).hexdigest())
    )

    assert "checksum mismatch" in audit.loc[0, "issues"]
    assert "checksum differs from locked evidence" in audit.loc[0, "issues"]


def test_visible_text_ignores_script_content() -> None:
    content = b"<html><script>secret</script><body> visible text </body></html>"

    text = extract_visible_text(content)

    assert text == "visibletext"
    assert "secret" not in text


def test_evidence_contract_rejects_non_official_domain(tmp_path: Path) -> None:
    catalog = _catalog()
    catalog.loc[0, "source_url"] = "https://example.com/release.html"
    archive = MacroEvidenceArchive(
        tmp_path, session=FakeSession(), sleep=lambda _: None
    )

    try:
        archive.fetch_catalog(catalog, _evidence())
    except ValueError as exc:
        assert "domain is not allowed" in str(exc)
    else:
        raise AssertionError("non-official macro source must be rejected")
