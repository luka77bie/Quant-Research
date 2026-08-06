from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

import narrative_regime.narrative.sections as sections
from narrative_regime.narrative.sections import (
    parse_policy_sections,
    section_summary,
)


def _extraction(root: Path, text: str) -> pd.DataFrame:
    path = root / "data/processed/narrative_text/report.txt"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    return pd.DataFrame(
        [
            {
                "record_id": "report",
                "source_id": "central_bank",
                "quality_status": "ready",
                "point_in_time_status": "provisional",
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "text_path": str(path),
            }
        ]
    )


def test_parser_uses_last_exact_heading(tmp_path: Path, monkeypatch) -> None:
    text = (
        "目录\n二、下一阶段主要政策思路\n其他目录\n"
        "正文\n二、下一阶段主要政策思路\n" + "政策" * 100 + "\n"
    )
    monkeypatch.setattr(
        sections,
        "extract_catalog_text",
        lambda root, catalog, sources: _extraction(root, text),
    )

    result = parse_policy_sections(
        tmp_path,
        pd.DataFrame(),
        pd.DataFrame(),
        minimum_characters=100,
        maximum_characters=300,
    )

    assert result.loc[0, "quality_status"] == "ready"
    assert result.loc[0, "heading_occurrence_count"] == 2
    assert Path(result.loc[0, "section_path"]).read_text().startswith("政策政策")
    assert "正文" not in Path(result.loc[0, "section_path"]).read_text()


def test_parser_accepts_new_heading_and_whitespace(tmp_path: Path, monkeypatch) -> None:
    text = "二、 下一阶段货币政策主要思路  \n" + "政策" * 100 + "\n"
    monkeypatch.setattr(
        sections,
        "extract_catalog_text",
        lambda root, catalog, sources: _extraction(root, text),
    )

    result = parse_policy_sections(
        tmp_path,
        pd.DataFrame(),
        pd.DataFrame(),
        minimum_characters=100,
        maximum_characters=300,
    )

    assert result.loc[0, "quality_status"] == "ready"
    assert result.loc[0, "matched_heading"] == "二、下一阶段货币政策主要思路"


def test_missing_heading_is_blocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        sections,
        "extract_catalog_text",
        lambda root, catalog, sources: _extraction(root, "政策" * 100),
    )

    result = parse_policy_sections(
        tmp_path,
        pd.DataFrame(),
        pd.DataFrame(),
        minimum_characters=1,
        maximum_characters=300,
    )

    assert result.loc[0, "quality_status"] == "blocked"
    assert "heading not found" in result.loc[0, "quality_issues"]


def test_valid_cache_skips_section_parse(tmp_path: Path, monkeypatch) -> None:
    text = "二、下一阶段主要政策思路\n" + "政策" * 100 + "\n"
    extraction = _extraction(tmp_path, text)
    monkeypatch.setattr(
        sections, "extract_catalog_text", lambda root, catalog, sources: extraction
    )
    parse_policy_sections(
        tmp_path,
        pd.DataFrame(),
        pd.DataFrame(),
        minimum_characters=100,
        maximum_characters=300,
    )
    section_path = tmp_path / "data/processed/narrative_sections/report.txt"
    metadata = json.loads(section_path.with_suffix(".meta.json").read_text())

    result = parse_policy_sections(
        tmp_path,
        pd.DataFrame(),
        pd.DataFrame(),
        minimum_characters=100,
        maximum_characters=300,
    )

    assert result.loc[0, "cache_status"] == "cached"
    assert result.loc[0, "section_sha256"] == metadata["section_sha256"]


def test_summary_passes_at_thirty_ready_records() -> None:
    results = pd.DataFrame(
        {
            "quality_status": ["ready"] * 30 + ["blocked"] * 2,
            "character_count": [100] * 32,
        }
    )

    summary = section_summary(results)

    assert summary["section_gate"] == "pass"
    assert summary["ready_records"] == 30
    assert summary["research_use"] == "exploratory_only"
