# Idea Card v0.1

## Thesis

Point-in-time narrative information may add incremental value to a frozen
Chinese ETF momentum strategy only in identifiable uncertainty and liquidity
regimes, rather than unconditionally across the full sample.

## Smallest worthwhile claim

A pre-specified narrative signal changes allocation or drawdown behaviour in a
held-out regime without losing its contribution after realistic delay, costs,
and simple price-based controls.

## Baselines

- Frozen MOM60 monthly Top-3.
- MOM60 plus the predecessor market-attention proxy.
- Macro-regime-conditioned MOM60 without narrative inputs.
- Narrative-conditioned allocation with shuffled or lagged narrative labels.

## Evaluation

- Walk-forward out-of-sample CAGR, Sharpe, Sortino, max drawdown, and Calmar.
- Turnover and cost sensitivity at 10, 20, and 30 basis points.
- Regime and ETF-family attribution.
- Ablations for macro regime, narrative signal, and their interaction.
- Confidence intervals or block bootstrap where sample size permits.

## Assumption-based score

| Dimension | Score | Evidence |
| --- | ---: | --- |
| Novelty | 3 | Conditional narrative value is sharper than another sentiment strategy, but related work still needs auditing. |
| Feasibility | 3 | Market data is manageable; point-in-time Chinese narrative data is the main blocker. |
| Evaluation | 4 | The predecessor supplies a frozen baseline and a clear negative result. |
| Career relevance | 5 | Demonstrates strategy research, data discipline, attribution, and honest model rejection. |
| Research quality risk | 2 | Few regimes and flexible narrative definitions create substantial overfitting risk. |

## Decision

`revise-and-keep`: proceed with the data-reliability and baseline milestones.
Do not implement an LLM narrative model until a reproducible point-in-time
archive passes the data audit.

## Fastest falsification test

Reproduce MOM60 on a common, fully audited ETF panel and verify that the old
market-attention proxy's defensive 2022-2023 behaviour survives the new data
pipeline. Stop or redesign if the predecessor result cannot be reproduced.
