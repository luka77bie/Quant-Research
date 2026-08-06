from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

import narrative_regime.narrative.features as features
from narrative_regime.narrative.features import (
    _character_bigram_cosine,
    build_policy_features,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _sections(root: Path) -> pd.DataFrame:
    rows = []
    for record_id, text in [("q1", "宽松政策科技创新"), ("q2", "宽松政策金融稳定")]:
        path = root / "data/processed/narrative_sections" / f"{record_id}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        rows.append(
            {
                "record_id": record_id,
                "quality_status": "ready",
                "point_in_time_status": "provisional",
                "section_sha256": record_id * 32,
                "section_path": str(path),
            }
        )
    return pd.DataFrame(rows)


def _catalog() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "record_id": "q2",
                "period_end": "2020-06-30",
                "published_at": "2020-08-01T09:00:00+08:00",
                "available_at": "2020-08-02T09:00:00+08:00",
            },
            {
                "record_id": "q1",
                "period_end": "2020-03-31",
                "published_at": "2020-05-01T09:00:00+08:00",
                "available_at": "2020-05-02T09:00:00+08:00",
            },
        ]
    )


def _lexicon() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"category": "stance", "term": "宽松", "rationale": "stance"},
            {"category": "target", "term": "科技创新", "rationale": "target"},
            {"category": "target", "term": "金融稳定", "rationale": "target"},
        ]
    )


def test_features_are_sorted_return_blind_and_auditable(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        features,
        "parse_policy_sections",
        lambda root, catalog, sources: _sections(root),
    )

    result = build_policy_features(tmp_path, _catalog(), pd.DataFrame(), _lexicon())

    assert result.features["record_id"].tolist() == ["q1", "q2"]
    assert result.features["available_at"].tolist()[0].startswith("2020-05-02")
    assert result.features["term_count_stance"].tolist() == [1, 1]
    assert result.features["term_count_target"].tolist() == [1, 1]
    assert math.isnan(result.features.loc[0, "prior_section_similarity"])
    assert result.features.loc[1, "prior_section_similarity"] > 0
    assert result.summary["return_data_used"] is False
    assert result.summary["composite_score_created"] is False


def test_duplicate_normalized_terms_are_rejected(tmp_path: Path) -> None:
    lexicon = _lexicon()
    lexicon.loc[1, "term"] = "宽 松"

    with pytest.raises(ValueError, match="duplicate normalized terms"):
        build_policy_features(tmp_path, _catalog(), pd.DataFrame(), lexicon)


def test_character_bigram_cosine_boundaries() -> None:
    assert _character_bigram_cosine("政策稳定", "政策稳定") == pytest.approx(1)
    assert _character_bigram_cosine("政策稳定", "完全不同") == pytest.approx(0)
    assert math.isnan(_character_bigram_cosine("政", "政策"))


def test_frozen_policy_lexicon_is_unique_and_complete() -> None:
    lexicon = pd.read_csv(PROJECT_ROOT / "configs/policy_term_lexicon.csv")

    assert len(lexicon) == 25
    assert set(lexicon["category"]) == {
        "accommodation",
        "restraint",
        "risk_control",
        "fx_stability",
        "structural_support",
    }
    assert not lexicon["term"].str.replace(r"\s+", "", regex=True).duplicated().any()
    assert lexicon["rationale"].str.strip().ne("").all()
