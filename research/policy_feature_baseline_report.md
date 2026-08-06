# Return-Blind Policy Feature Baseline v0.1

## Decision

The transparent non-LLM feature gate passes. The output is suitable for lagged
publication-time joins and descriptive stability checks. It is not yet a trading
signal and does not resolve point-in-time revision risk.

## Frozen Inputs and Transformations

- Corpus: 32 audited forward-looking policy sections.
- Lexicon: 25 literal terms in `configs/policy_term_lexicon.csv`.
- Categories: accommodation, restraint, financial risk control, exchange-rate
  stability, and structural support.
- Normalization: remove whitespace, then count exact literal occurrences.
- Scale: report raw counts and counts per 1,000 section characters.
- Change: report quarter-over-quarter density and section-length changes.
- Similarity: cosine similarity of Chinese character-bigram count vectors to the
  immediately prior report.
- Timing: retain official `published_at`, conservative `available_at`, and
  `provisional` point-in-time status on every row.

No return series, ETF selection, parameter search, feature weighting, composite
score, sentiment label, or LLM output enters this stage.

## Corpus Audit

| Category | Total counts | Nonzero quarters |
| --- | ---: | ---: |
| Accommodation | 75 | 31 |
| Restraint | 10 | 8 |
| Financial risk control | 120 | 32 |
| Exchange-rate stability | 73 | 30 |
| Structural support | 256 | 32 |

All 32 feature rows were produced, with 31 valid prior-quarter comparisons.
Prior-section cosine similarity ranges from 0.8257 to 0.9478 and averages
0.9006. The largest measured novelty occurs in 2019 Q4, followed by 2020 Q3 and
2020 Q1. This is a descriptive corpus result, not evidence of market relevance.

## Known Weaknesses

- Restraint language is sparse and unsuitable for fine-grained continuous
  interpretation without further validation.
- `降息`, `防止资金空转`, and `房住不炒` have zero counts. They remain frozen
  to prevent corpus-driven dictionary replacement.
- Literal phrases miss synonyms and can count references that do not express the
  report's own stance.
- Structural-support terms are broader and more frequent than stance terms, so
  raw category levels are not directly comparable.
- Character-bigram novelty detects wording changes but cannot distinguish policy
  substance from drafting or template changes.

## Next Gate

1. Freeze 24-hour, 48-hour, and next-month timing joins before reading market
   relationships. This gate passed with zero lookahead violations; see
   `research/narrative_timing_protocol_report.md`.
2. Produce descriptive feature stability, missingness, and correlation audits;
   do not select features using future returns.
3. Evaluate every frozen category and the similarity control, including sparse
   and zero-count terms in the audit appendix.
4. Do not build a composite or add an LLM representation unless the transparent
   baseline yields an interpretable, stable measurement result.
