# Study 02 Idea Card: China Macro Regime ETF Atlas

## Research Question

How do liquid Chinese ETF asset groups behave across pre-defined growth,
inflation, and liquidity regimes after respecting each macro release date and
each ETF's dynamic availability?

## Economic Mechanism

Growth conditions should change equity and sector earnings expectations,
inflation should alter real-rate and commodity exposure, and liquidity should
change discount rates and financing-sensitive risk appetite. These mechanisms
may explain cross-asset payoff differences without assuming a text model can
forecast returns.

## Smallest Worthwhile Claim

A return-blind, economically interpretable regime chronology is reproducible
from point-in-time available macro observations and reveals payoff differences
that survive timing sensitivity. This claim is descriptive; it does not imply a
tradable allocation.

## Baselines

- Unconditional equal-weight ETF-group returns.
- The frozen monthly MOM60 Top-3 baseline.
- Single-dimension growth, inflation, and liquidity states before any combined
  regime.

## Design Priorities

1. Freeze official series, transformations, and release lags.
2. Build a vintage and revision-risk ledger before market joins.
3. Prefer threshold states with direct economic meaning over unsupervised
   clusters.
4. Require minimum regime counts before estimating a payoff cell.
5. Separate the payoff atlas from a later allocation rule.

## Main Risks

- Revised macro histories can create hidden lookahead.
- Three regime dimensions can create too many cells for an eight-year sample.
- Regime persistence and overlapping returns reduce effective sample size.
- A state can proxy for one crisis episode rather than a repeatable mechanism.
- The same ETF data cannot serve unlimited rounds of threshold selection.

## Assumption-Based Score

| Dimension | Score | Reason |
| --- | ---: | --- |
| Novelty | 3/5 | Regime payoff maps are established; China release-time provenance and dynamic ETF eligibility create the useful distinction |
| Feasibility | 3/5 | Market infrastructure exists, but official macro vintages and release timestamps may block strict reconstruction |
| Evaluation | 4/5 | Single dimensions, unconditional payoffs, and frozen MOM60 provide clear baselines and failure comparisons |
| Career relevance | 5/5 | Directly demonstrates macro reasoning, systematic validation, ETF allocation, and research judgment |
| Research risk | High | Flexible thresholds, revised data, persistent states, and few independent cycles can create false regime stories |

Current decision: `keep, subject to a data-feasibility pilot`.

## Fastest Falsification Test

Before building a regime engine, select one growth, one inflation, and one
liquidity series and audit 12 historical releases. Require an original release
date, the value available at that date, revision status, and a reproducible
source. Park the study if fewer than 10 of 12 observations pass without using a
current revised history as though it were point-in-time data.

## Stop Conditions

- Original release timing or vintage status cannot be established.
- A regime definition requires forward ETF returns to choose its threshold.
- Fewer than eight independent monthly observations occupy a reported state.
- Combined states are not more interpretable than their single dimensions.
- Any proposed allocation depends on one crisis or one ETF family.
