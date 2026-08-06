from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path

import pandas as pd
import pypdf
from pypdf import PdfReader

from narrative_regime.narrative.archive import audit_archive


def extract_catalog_text(
    root: Path,
    catalog: pd.DataFrame,
    sources: pd.DataFrame,
    *,
    minimum_characters: int = 10_000,
    maximum_empty_page_ratio: float = 0.10,
    maximum_replacement_ratio: float = 0.001,
    minimum_cjk_ratio: float = 0.50,
) -> pd.DataFrame:
    """Extract deterministic text from every archive-ready PDF."""
    if minimum_characters < 1:
        raise ValueError("minimum_characters must be at least 1")
    for name, value in {
        "maximum_empty_page_ratio": maximum_empty_page_ratio,
        "maximum_replacement_ratio": maximum_replacement_ratio,
        "minimum_cjk_ratio": minimum_cjk_ratio,
    }.items():
        if not 0 <= value <= 1:
            raise ValueError(f"{name} must be between 0 and 1")
    audit = audit_archive(root, catalog, sources)
    blocked = audit.loc[audit["archive_status"].ne("ready"), "record_id"]
    if not blocked.empty:
        raise ValueError(
            "narrative archive contains blocked records: " + ", ".join(blocked)
        )
    rows = []
    for record in audit.to_dict("records"):
        record_id = str(record["record_id"])
        source_id = str(record["source_id"])
        pdf_path = (
            root
            / "data"
            / "raw"
            / "narrative"
            / source_id
            / f"{record_id}.pdf"
        )
        text_path = root / "data" / "processed" / "narrative_text" / f"{record_id}.txt"
        metadata_path = text_path.with_suffix(".meta.json")
        cached = _read_valid_cache(
            text_path, metadata_path, str(record["sha256"])
        )
        if cached is None:
            pages = [
                _normalize_text(page.extract_text() or "")
                for page in PdfReader(pdf_path).pages
            ]
            text = "\n\f\n".join(pages).strip() + "\n"
            page_count = len(pages)
            empty_pages = sum(not _non_whitespace(page) for page in pages)
            metadata = _write_text_cache(
                text_path,
                metadata_path,
                text,
                source_sha256=str(record["sha256"]),
                page_count=page_count,
                empty_pages=empty_pages,
            )
            cache_status = "extracted"
        else:
            metadata = cached
            cache_status = "cached"
        quality_issues = _quality_issues(
            metadata,
            minimum_characters=minimum_characters,
            maximum_empty_page_ratio=maximum_empty_page_ratio,
            maximum_replacement_ratio=maximum_replacement_ratio,
            minimum_cjk_ratio=minimum_cjk_ratio,
        )
        rows.append(
            {
                "record_id": record_id,
                "source_id": source_id,
                "cache_status": cache_status,
                "quality_status": "ready" if not quality_issues else "blocked",
                "point_in_time_status": record["point_in_time_status"],
                **metadata,
                "quality_issues": "; ".join(quality_issues),
            }
        )
    result = pd.DataFrame(rows)
    duplicate_hash = result["text_sha256"].duplicated(keep=False)
    result.loc[duplicate_hash, "quality_status"] = "blocked"
    result.loc[duplicate_hash, "quality_issues"] = result.loc[
        duplicate_hash, "quality_issues"
    ].map(lambda value: "; ".join(filter(None, [value, "duplicate text hash"])))
    return result


def extraction_summary(results: pd.DataFrame) -> dict[str, object]:
    return {
        "records": len(results),
        "ready_records": int(results["quality_status"].eq("ready").sum()),
        "blocked_records": int(results["quality_status"].ne("ready").sum()),
        "total_pages": int(results["page_count"].sum()),
        "total_characters": int(results["character_count"].sum()),
        "provisional_records": int(
            results["point_in_time_status"].eq("provisional").sum()
        ),
        "extraction_gate": (
            "pass" if results["quality_status"].eq("ready").all() else "blocked"
        ),
        "research_use": "exploratory_only",
    }


def _normalize_text(value: str) -> str:
    value = (
        unicodedata.normalize("NFKC", value)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.split("\n")]
    return "\n".join(lines).strip()


def _write_text_cache(
    text_path: Path,
    metadata_path: Path,
    text: str,
    *,
    source_sha256: str,
    page_count: int,
    empty_pages: int,
) -> dict[str, object]:
    text_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = text.encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=text_path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
    os.replace(temporary, text_path)
    character_count = len(_non_whitespace(text))
    cjk_character_count = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", text))
    replacement_count = text.count("\ufffd")
    metadata = {
        "source_sha256": source_sha256,
        "extraction_schema_version": 1,
        "text_sha256": hashlib.sha256(encoded).hexdigest(),
        "extractor": "pypdf",
        "extractor_version": pypdf.__version__,
        "page_count": page_count,
        "empty_page_count": empty_pages,
        "empty_page_ratio": empty_pages / page_count if page_count else 1.0,
        "character_count": character_count,
        "cjk_character_count": cjk_character_count,
        "cjk_character_ratio": (
            cjk_character_count / character_count if character_count else 0.0
        ),
        "replacement_character_count": replacement_count,
        "replacement_character_ratio": (
            replacement_count / character_count if character_count else 1.0
        ),
        "text_path": str(text_path),
    }
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=text_path.parent, delete=False
    ) as handle:
        temporary_metadata = Path(handle.name)
        json.dump(metadata, handle, ensure_ascii=True, indent=2)
        handle.write("\n")
    os.replace(temporary_metadata, metadata_path)
    return metadata


def _read_valid_cache(
    text_path: Path, metadata_path: Path, source_sha256: str
) -> dict[str, object] | None:
    if not text_path.exists() or not metadata_path.exists():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        return (
            metadata
            if metadata["extraction_schema_version"] == 1
            and metadata["source_sha256"] == source_sha256
            and metadata["text_sha256"] == _sha256(text_path)
            else None
        )
    except (KeyError, json.JSONDecodeError, OSError):
        return None


def _quality_issues(
    metadata: dict[str, object],
    *,
    minimum_characters: int,
    maximum_empty_page_ratio: float,
    maximum_replacement_ratio: float,
    minimum_cjk_ratio: float,
) -> list[str]:
    issues = []
    if int(metadata["page_count"]) < 1:
        issues.append("no PDF pages")
    if int(metadata["character_count"]) < minimum_characters:
        issues.append("too few extracted characters")
    if float(metadata["empty_page_ratio"]) > maximum_empty_page_ratio:
        issues.append("too many empty pages")
    if float(metadata["replacement_character_ratio"]) > maximum_replacement_ratio:
        issues.append("too many replacement characters")
    if float(metadata["cjk_character_ratio"]) < minimum_cjk_ratio:
        issues.append("too few CJK characters")
    return issues


def _non_whitespace(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
