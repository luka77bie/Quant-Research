from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

import pandas as pd

from narrative_regime.narrative.extraction import extract_catalog_text

PARSER_SCHEMA_VERSION = 1
POLICY_SECTION_HEADINGS = {
    "二、下一阶段主要政策思路",
    "二、下一阶段货币政策主要思路",
}


def parse_policy_sections(
    root: Path,
    catalog: pd.DataFrame,
    sources: pd.DataFrame,
    *,
    minimum_characters: int = 1_500,
    maximum_characters: int = 6_000,
    minimum_cjk_ratio: float = 0.60,
) -> pd.DataFrame:
    """Parse the final forward-looking policy section from audited report text."""
    if minimum_characters < 1:
        raise ValueError("minimum_characters must be at least 1")
    if maximum_characters < minimum_characters:
        raise ValueError("maximum_characters must be at least minimum_characters")
    if not 0 <= minimum_cjk_ratio <= 1:
        raise ValueError("minimum_cjk_ratio must be between 0 and 1")

    extraction = extract_catalog_text(root, catalog, sources)
    blocked = extraction.loc[extraction["quality_status"].ne("ready"), "record_id"]
    if not blocked.empty:
        raise ValueError(
            "narrative extraction contains blocked records: " + ", ".join(blocked)
        )

    rows = []
    for record in extraction.to_dict("records"):
        text_path = Path(str(record["text_path"]))
        section_path = (
            root
            / "data"
            / "processed"
            / "narrative_sections"
            / f"{record['record_id']}.txt"
        )
        metadata_path = section_path.with_suffix(".meta.json")
        cached = _read_valid_cache(
            section_path,
            metadata_path,
            source_text_sha256=str(record["text_sha256"]),
        )
        if cached is None:
            metadata = _parse_and_write_section(
                text_path,
                section_path,
                metadata_path,
                source_text_sha256=str(record["text_sha256"]),
            )
            cache_status = "parsed"
        else:
            metadata = cached
            cache_status = "cached"

        issues = _quality_issues(
            metadata,
            minimum_characters=minimum_characters,
            maximum_characters=maximum_characters,
            minimum_cjk_ratio=minimum_cjk_ratio,
        )
        rows.append(
            {
                "record_id": record["record_id"],
                "source_id": record["source_id"],
                "cache_status": cache_status,
                "quality_status": "ready" if not issues else "blocked",
                "point_in_time_status": record["point_in_time_status"],
                **metadata,
                "quality_issues": "; ".join(issues),
            }
        )

    result = pd.DataFrame(rows)
    valid_hash = result["section_sha256"].ne("")
    duplicates = valid_hash & result["section_sha256"].duplicated(keep=False)
    result.loc[duplicates, "quality_status"] = "blocked"
    result.loc[duplicates, "quality_issues"] = result.loc[
        duplicates, "quality_issues"
    ].map(lambda value: "; ".join(filter(None, [value, "duplicate section hash"])))
    return result


def section_summary(results: pd.DataFrame) -> dict[str, object]:
    ready = results["quality_status"].eq("ready")
    return {
        "records": len(results),
        "ready_records": int(ready.sum()),
        "blocked_records": int((~ready).sum()),
        "total_characters": int(results.loc[ready, "character_count"].sum()),
        "minimum_required_ready_records": 30,
        "section_gate": "pass" if int(ready.sum()) >= 30 else "blocked",
        "research_use": "exploratory_only",
    }


def _parse_and_write_section(
    text_path: Path,
    section_path: Path,
    metadata_path: Path,
    *,
    source_text_sha256: str,
) -> dict[str, object]:
    text = text_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    matches = [
        (index, _canonical_heading(line))
        for index, line in enumerate(lines)
        if _canonical_heading(line) in POLICY_SECTION_HEADINGS
    ]
    if matches:
        heading_index, heading = matches[-1]
        section = "".join(lines[heading_index + 1 :]).strip() + "\n"
    else:
        heading = ""
        section = ""

    section_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = section.encode("utf-8")
    _atomic_write_bytes(section_path, encoded)
    non_whitespace = re.sub(r"\s+", "", section)
    cjk_count = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", section))
    metadata = {
        "source_text_sha256": source_text_sha256,
        "parser_schema_version": PARSER_SCHEMA_VERSION,
        "matched_heading": heading,
        "heading_occurrence_count": len(matches),
        "section_sha256": hashlib.sha256(encoded).hexdigest() if section else "",
        "character_count": len(non_whitespace),
        "cjk_character_count": cjk_count,
        "cjk_character_ratio": (
            cjk_count / len(non_whitespace) if non_whitespace else 0.0
        ),
        "source_character_count": len(re.sub(r"\s+", "", text)),
        "section_character_ratio": (
            len(non_whitespace) / len(re.sub(r"\s+", "", text)) if text else 0.0
        ),
        "section_path": str(section_path),
    }
    _atomic_write_json(metadata_path, metadata)
    return metadata


def _canonical_heading(line: str) -> str:
    return re.sub(r"\s+", "", line)


def _quality_issues(
    metadata: dict[str, object],
    *,
    minimum_characters: int,
    maximum_characters: int,
    minimum_cjk_ratio: float,
) -> list[str]:
    issues = []
    if not metadata["matched_heading"]:
        issues.append("policy section heading not found")
    if int(metadata["character_count"]) < minimum_characters:
        issues.append("policy section too short")
    if int(metadata["character_count"]) > maximum_characters:
        issues.append("policy section too long")
    if float(metadata["cjk_character_ratio"]) < minimum_cjk_ratio:
        issues.append("policy section has too few CJK characters")
    return issues


def _read_valid_cache(
    section_path: Path,
    metadata_path: Path,
    *,
    source_text_sha256: str,
) -> dict[str, object] | None:
    if not section_path.exists() or not metadata_path.exists():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        expected_hash = hashlib.sha256(section_path.read_bytes()).hexdigest()
        return (
            metadata
            if metadata["parser_schema_version"] == PARSER_SCHEMA_VERSION
            and metadata["source_text_sha256"] == source_text_sha256
            and metadata["section_sha256"] == expected_hash
            else None
        )
    except (KeyError, json.JSONDecodeError, OSError):
        return None


def _atomic_write_bytes(path: Path, value: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(value)
    os.replace(temporary, path)


def _atomic_write_json(path: Path, value: dict[str, object]) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, ensure_ascii=True, indent=2)
        handle.write("\n")
    os.replace(temporary, path)
