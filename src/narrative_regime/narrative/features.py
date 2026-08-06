from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from narrative_regime.narrative.archive import audit_archive
from narrative_regime.narrative.sections import parse_policy_sections

LEXICON_COLUMNS = {"category", "term", "rationale"}


@dataclass(frozen=True)
class PolicyFeatureResult:
    features: pd.DataFrame
    term_counts: pd.DataFrame
    summary: dict[str, object]


def build_policy_features(
    root: Path,
    catalog: pd.DataFrame,
    sources: pd.DataFrame,
    lexicon: pd.DataFrame,
) -> PolicyFeatureResult:
    """Build frozen, return-blind diagnostics from audited policy sections."""
    _validate_lexicon(lexicon)
    sections = parse_policy_sections(root, catalog, sources)
    blocked = sections.loc[sections["quality_status"].ne("ready"), "record_id"]
    if not blocked.empty:
        raise ValueError(
            "policy sections contain blocked records: " + ", ".join(blocked)
        )

    metadata = _availability_metadata(root, catalog, sources)
    records = sections.merge(metadata, on="record_id", validate="one_to_one")
    records["period_end"] = pd.to_datetime(records["period_end"])
    records = records.sort_values("period_end").reset_index(drop=True)
    categories = list(dict.fromkeys(lexicon["category"].astype(str)))

    feature_rows = []
    count_rows = []
    previous_text: str | None = None
    previous_feature: dict[str, object] | None = None
    for record in records.to_dict("records"):
        text = _compact_text(Path(str(record["section_path"])).read_text())
        character_count = len(text)
        row: dict[str, object] = {
            "record_id": record["record_id"],
            "period_end": record["period_end"].date().isoformat(),
            "published_at": record["published_at"],
            "available_at": record["available_at"],
            "point_in_time_status": record["point_in_time_status"],
            "section_sha256": record["section_sha256"],
            "section_character_count": character_count,
        }
        for category in categories:
            category_count = 0
            selected = lexicon.loc[lexicon["category"].eq(category)]
            for term_record in selected.to_dict("records"):
                term = _compact_text(str(term_record["term"]))
                count = text.count(term)
                category_count += count
                count_rows.append(
                    {
                        "record_id": record["record_id"],
                        "period_end": record["period_end"].date().isoformat(),
                        "category": category,
                        "term": term_record["term"],
                        "count": count,
                    }
                )
            row[f"term_count_{category}"] = category_count
            row[f"term_density_per_1000_{category}"] = (
                category_count * 1000 / character_count
            )

        similarity = (
            _character_bigram_cosine(text, previous_text)
            if previous_text is not None
            else math.nan
        )
        row["prior_section_similarity"] = similarity
        row["section_novelty"] = (
            1 - similarity if not math.isnan(similarity) else math.nan
        )
        row["section_character_change_qoq"] = (
            character_count - int(previous_feature["section_character_count"])
            if previous_feature is not None
            else math.nan
        )
        for category in categories:
            column = f"term_density_per_1000_{category}"
            row[f"{column}_change_qoq"] = (
                float(row[column]) - float(previous_feature[column])
                if previous_feature is not None
                else math.nan
            )
        feature_rows.append(row)
        previous_text = text
        previous_feature = row

    features = pd.DataFrame(feature_rows)
    term_counts = pd.DataFrame(count_rows)
    summary = {
        "records": len(features),
        "categories": categories,
        "terms": len(lexicon),
        "prior_comparisons": int(features["prior_section_similarity"].notna().sum()),
        "feature_gate": "pass" if len(features) == len(catalog) else "blocked",
        "return_data_used": False,
        "composite_score_created": False,
        "research_use": "exploratory_only",
    }
    return PolicyFeatureResult(features, term_counts, summary)


def _availability_metadata(
    root: Path,
    catalog: pd.DataFrame,
    sources: pd.DataFrame,
) -> pd.DataFrame:
    columns = ["record_id", "period_end", "published_at", "available_at"]
    if set(columns).issubset(catalog.columns):
        return catalog[columns].copy()
    archive = audit_archive(root, catalog, sources)
    return archive[columns].copy()


def _validate_lexicon(lexicon: pd.DataFrame) -> None:
    missing = sorted(LEXICON_COLUMNS - set(lexicon.columns))
    if missing:
        raise ValueError("lexicon missing columns: " + ", ".join(missing))
    if lexicon.empty:
        raise ValueError("lexicon must contain at least one term")
    empty_fields = lexicon[list(LEXICON_COLUMNS)].apply(
        lambda column: column.astype(str).str.strip().eq("")
    )
    if empty_fields.any().any():
        raise ValueError("lexicon fields must not be empty")
    if lexicon["term"].map(_compact_text).duplicated().any():
        raise ValueError("lexicon contains duplicate normalized terms")
    invalid_categories = sorted(
        {
            category
            for category in lexicon["category"].astype(str)
            if re.fullmatch(r"[a-z][a-z0-9_]*", category) is None
        }
    )
    if invalid_categories:
        raise ValueError("invalid lexicon categories: " + ", ".join(invalid_categories))


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _character_bigram_cosine(left: str, right: str) -> float:
    left_counts = Counter(left[index : index + 2] for index in range(len(left) - 1))
    right_counts = Counter(
        right[index : index + 2] for index in range(len(right) - 1)
    )
    if not left_counts or not right_counts:
        return math.nan
    numerator = sum(
        count * right_counts.get(token, 0) for token, count in left_counts.items()
    )
    left_norm = math.sqrt(sum(count**2 for count in left_counts.values()))
    right_norm = math.sqrt(sum(count**2 for count in right_counts.values()))
    return numerator / (left_norm * right_norm)
