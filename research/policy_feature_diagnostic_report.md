# Policy Feature Stability Diagnostic v0.1

## Decision

The feature-stability gate passes. The frozen market relationship protocol may
be run next, but the small quarterly sample, sparse restraint language, and
measurement redundancy require conservative interpretation.

## Audit Scope

All 19 numeric columns are audited. The process checks distribution,
missingness, infinite values, zero variance, lag-one quarterly persistence, and
full Pearson and Spearman correlation matrices. It reads no market or return
data and performs no performance-based feature selection.

## Result

| Check | Result |
| --- | ---: |
| Quarterly records | 32 |
| Numeric features | 19 |
| Expected missing observations | 8 |
| Actual missing observations | 8 |
| Unexpected missing observations | 0 |
| Infinite observations | 0 |
| Zero-variance features | 0 |
| Absolute Spearman >= 0.90 pairs | 6 |

The eight missing values are the first observation for prior similarity,
novelty, section-length change, and five term-density changes.

## Redundancy Decision

Five high-correlation pairs link each raw category count to its corresponding
per-1,000-character density. The sixth is exact by construction:
`section_novelty = 1 - prior_section_similarity`.

Before observing returns, feature roles are frozen as follows:

- Primary levels: five term densities and prior-section similarity.
- Primary changes: five quarter-over-quarter term-density changes.
- Measurement controls: section length and its quarter-over-quarter change.
- Audit-only redundant views: five raw counts and section novelty.

Raw counts and novelty remain in all diagnostic outputs. They are not silently
dropped and cannot be substituted back based on future performance.

## Persistence and Limits

Exchange-rate language is the most persistent category: lag-one Spearman is
about 0.82 for raw count and 0.79 for density. Structural-support density has
lag-one Spearman near 0.52. Density-change features are much less persistent and
mostly mean-reverting. With only 32 reports, these estimates are descriptive and
not statistically stable enough to justify a predictive claim.

## Frozen Next Stage

`configs/market_relation_protocol.json` was committed before market outcomes are
computed. It requires all combinations of three delays and 5, 20, and 60
reference-session windows, Tencent qfq close-to-close returns, dynamic listing
eligibility, tradable endpoints, lagged momentum and volatility controls, and
asset-group reporting. It prohibits specification selection and portfolio
construction.
