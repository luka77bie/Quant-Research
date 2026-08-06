# Market-Attention Control Reproduction v0.1

## Decision

The predecessor's 2022-2023 defensive direction is reproduced, but the proxy
is not promoted to a narrative signal. It remains a market-data control for
later incremental tests. Its weights must not be tuned further on this sample.

## Frozen Design

- Sample: qualified Tencent panel, 18 ETFs, 35,372 long-form rows.
- Invested range: 2018-05-02 to 2026-07-31.
- Code commit: `a5195be5ad8bdb029f3e208e4ad98071f70ea217`.
- Manifest worktree state: clean.
- Short and long windows: 20 and 60 sessions.
- Feature weights: activity growth 40%, volume growth 25%, activity surprise
  25%, volatility expansion 10%.
- Composite: 50% cross-sectional MOM60 z-score and 50% attention z-score.
- Portfolio: monthly Top-3, equal target weight, 10 bps one-way turnover cost.
- No parameter was selected after observing this sample.

The predecessor used AKShare transaction value, named `turnover`. Tencent does
not provide transaction value, so 35,364 observed rows use `close * volume` as
an activity-value proxy. Eight verified no-trade rows retain their explicit
synthetic zero and are labelled separately. This is a directional reproduction,
not an exact data reproduction.

## Results

| Period | Model | Annual return | Sharpe | Maximum drawdown | Turnover |
| --- | --- | ---: | ---: | ---: | ---: |
| Full | MOM60 | 9.68% | 0.486 | -42.02% | 49.16 |
| Full | MOM60 + attention | 10.08% | 0.512 | -49.61% | 53.45 |
| Pre-2022 | MOM60 | 29.84% | 1.095 | -27.68% | 21.66 |
| Pre-2022 | MOM60 + attention | 18.50% | 0.774 | -33.81% | 22.64 |
| 2022-2023 | MOM60 | -16.62% | -1.123 | -33.35% | 12.73 |
| 2022-2023 | MOM60 + attention | -13.14% | -0.858 | -28.61% | 13.42 |
| 2024+ | MOM60 | 6.47% | 0.357 | -30.07% | 14.77 |
| 2024+ | MOM60 + attention | 19.00% | 0.762 | -24.46% | 17.39 |

The 2022-2023 annual loss improves by 3.48 percentage points and maximum
drawdown improves by 4.75 points. That matches the predecessor's reported
direction. However, pre-2022 performance deteriorates substantially, full-
sample maximum drawdown is 7.59 points worse, and 2024+ behavior reverses the
predecessor's reported underperformance. The composite changes at least one
holding in 84 of 99 rebalances, so it is economically active rather than a
near-duplicate rank.

## Interpretation

This passes a narrow directional reproduction test and fails a broad mechanism
or robustness claim. The features are transformations of price, volume, and
volatility. They contain no news, policy text, embeddings, model output, or
point-in-time narrative record. Improved performance therefore cannot be
attributed to narrative information or AI.

The result is sensitive to period and data construction. A modest full-sample
return and Sharpe gain does not compensate for the deeper full-sample drawdown,
higher turnover, and conflicting 2024+ behavior. Searching the old 0-50%
ablation grid again would be post-hoc optimization and is prohibited.

## Stop And Continue Conditions

- Stop: no more proxy-weight, feature-weight, or window tuning on this panel.
- Retain: use the fixed composite as a price/volume control or placebo only.
- Continue: a narrative model must use records with `published_at`,
  `retrieved_at`, and conservative `available_at` fields.
- Reject: any claimed narrative contribution that disappears after controlling
  for MOM60 and this fixed attention proxy.
- Stop the narrative branch if an auditable point-in-time archive cannot be
  assembled without relying on current-page backfills or unverifiable dates.

The next implementation gate is therefore data provenance for genuine text or
policy records, not another backtest variant.
