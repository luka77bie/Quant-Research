from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

import narrative_regime.narrative.extraction as extraction
from narrative_regime.narrative.extraction import (
    _normalize_text,
    extract_catalog_text,
    extraction_summary,
)

PDF_CONTENT = b"%PDF-1.4\nfixture"
PDF_SHA256 = hashlib.sha256(PDF_CONTENT).hexdigest()


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


def _catalog() -> pd.DataFrame:
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
                "expected_document_sha256": PDF_SHA256,
                "availability_evidence": "official_timestamped_index",
                "historical_snapshot_url": "",
                "historical_snapshot_sha256": "",
            }
        ]
    )


def _write_archive(root: Path) -> None:
    path = root / "data/raw/narrative/central_bank/report_2020_q4.pdf"
    path.parent.mkdir(parents=True)
    path.write_bytes(PDF_CONTENT)
    path.with_suffix(".meta.json").write_text(
        json.dumps(
            {
                "record_id": "report_2020_q4",
                "source_id": "central_bank",
                "document_url": "https://central.example/files/2020-q4.pdf",
                "retrieved_at": "2024-01-01T00:00:00+00:00",
                "bytes": len(PDF_CONTENT),
                "sha256": PDF_SHA256,
            }
        )
    )


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakeReader:
    def __init__(self, path: Path, pages: list[str]) -> None:
        self.pages = [FakePage(text) for text in pages]


def test_extraction_writes_quality_audited_text(
    tmp_path: Path, monkeypatch
) -> None:
    _write_archive(tmp_path)
    monkeypatch.setattr(
        extraction,
        "PdfReader",
        lambda path: FakeReader(path, ["A" * 80, "B" * 80]),
    )

    result = extract_catalog_text(
        tmp_path,
        _catalog(),
        _sources(),
        minimum_characters=100,
        minimum_cjk_ratio=0,
    )

    assert result.loc[0, "quality_status"] == "ready"
    assert result.loc[0, "page_count"] == 2
    assert result.loc[0, "character_count"] == 160
    assert Path(result.loc[0, "text_path"]).exists()


def test_valid_extraction_cache_skips_pdf_parser(
    tmp_path: Path, monkeypatch
) -> None:
    _write_archive(tmp_path)
    monkeypatch.setattr(
        extraction, "PdfReader", lambda path: FakeReader(path, ["A" * 200])
    )
    extract_catalog_text(
        tmp_path,
        _catalog(),
        _sources(),
        minimum_characters=100,
        minimum_cjk_ratio=0,
    )
    monkeypatch.setattr(
        extraction,
        "PdfReader",
        lambda path: (_ for _ in ()).throw(AssertionError("parser called")),
    )

    result = extract_catalog_text(
        tmp_path,
        _catalog(),
        _sources(),
        minimum_characters=100,
        minimum_cjk_ratio=0,
    )

    assert result.loc[0, "cache_status"] == "cached"


def test_empty_extraction_is_blocked(tmp_path: Path, monkeypatch) -> None:
    _write_archive(tmp_path)
    monkeypatch.setattr(
        extraction, "PdfReader", lambda path: FakeReader(path, [""])
    )

    result = extract_catalog_text(
        tmp_path,
        _catalog(),
        _sources(),
        minimum_characters=1,
        minimum_cjk_ratio=0,
    )

    assert result.loc[0, "quality_status"] == "blocked"
    assert "too few extracted characters" in result.loc[0, "quality_issues"]
    assert "too many empty pages" in result.loc[0, "quality_issues"]


def test_text_normalization_is_deterministic() -> None:
    assert _normalize_text("Ａ  B\r\n C\t D ") == "A B\nC D"


def test_non_cjk_gibberish_is_blocked(tmp_path: Path, monkeypatch) -> None:
    _write_archive(tmp_path)
    monkeypatch.setattr(
        extraction, "PdfReader", lambda path: FakeReader(path, ["A" * 200])
    )

    result = extract_catalog_text(
        tmp_path, _catalog(), _sources(), minimum_characters=100
    )

    assert result.loc[0, "quality_status"] == "blocked"
    assert "too few CJK characters" in result.loc[0, "quality_issues"]


def test_summary_keeps_exploratory_restriction(
    tmp_path: Path, monkeypatch
) -> None:
    _write_archive(tmp_path)
    monkeypatch.setattr(
        extraction, "PdfReader", lambda path: FakeReader(path, ["A" * 200])
    )
    result = extract_catalog_text(
        tmp_path,
        _catalog(),
        _sources(),
        minimum_characters=100,
        minimum_cjk_ratio=0,
    )

    summary = extraction_summary(result)

    assert summary["extraction_gate"] == "pass"
    assert summary["research_use"] == "exploratory_only"
    assert summary["provisional_records"] == 1
