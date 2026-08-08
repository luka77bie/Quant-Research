# Luka Quant Research Lab Roadmap v1.1

## Positioning

The lab demonstrates a strategy researcher's ability to connect economic
reasoning, market structure, data, and reproducible statistical testing. It is
not an attempt to build a large quant platform, high-frequency stack, or generic
factor zoo.

The distinguishing domain is:

> Chinese policy and macro information -> liquid ETF and cross-asset behaviour
> -> disciplined allocation or a documented decision not to trade.

This focus fits systematic-investing, securities proprietary-investment,
multi-asset, ETF, and quant-strategy research roles better than a broad list of
unrelated coding demonstrations.

## Scope Revision

The original v1.0 ambition of 20 research notes and eight projects creates a
quantity incentive before research quality is stable. Version 1.1 targets:

- Three flagship studies with distinct economic questions.
- Six polished research notes, including negative results.
- One common reproducibility and evidence standard.
- One lab-level GitHub entry page and project registry.
- No dashboard, machine-learning model, or extra data source without a research
  decision it is needed to support.

## Flagship Sequence

### Study 01: Narrative-Regime ETF Allocation

Question: does PBOC policy language add incremental information beyond a frozen
ETF momentum baseline and lagged market controls?

Decision: the infrastructure and falsification gates pass, but the current
32-report publication-time reconstruction produces no multiplicity-adjusted
candidate. The narrative portfolio is stopped. This study demonstrates data
provenance, benchmark discipline, leakage control, and honest model rejection.

### Study 02: China Macro Regime ETF Payoff Atlas

Question: how do broad equity, sector, bond, commodity, and overseas ETF groups
behave across pre-defined Chinese growth, inflation, and liquidity states?

Why it is next: it returns to the user's economics advantage and the lab's
regime-allocation thesis without reusing the exhausted narrative sample to tune
another text rule.

Initial design constraints:

- Use official or independently versioned monthly macro series.
- Define regime thresholds and release lags before reading forward ETF outcomes.
- Begin with interpretable states, not clustering or a hidden Markov model.
- Separate a descriptive payoff atlas from any allocation strategy.
- Compare regime information with the existing frozen MOM60 baseline only after
  the data and timing gates pass.

### Study 03: Scheduled Policy Event Research

Question: do pre-specified PBOC and major macro-release events produce repeatable
5-, 10-, and 20-session repricing across ETF groups?

This study starts only after Study 02. It must use scheduled event definitions,
explicit announcement timestamps, and the same no-silent-exclusion standard.

## Twelve-Week Plan

| Weeks | Deliverable | Gate |
| --- | --- | --- |
| 1-2 | Consolidate Study 01 note, code, manifests, and stop decision | A reviewer can reproduce the negative result |
| 3-4 | Freeze Study 02 macro-series, release-lag, and regime data contract | No ETF outcome has informed a threshold |
| 5-6 | Build and audit the point-in-time macro panel | Missing and revised observations are explicit |
| 7-8 | Publish a return-blind regime chronology and economic interpretation | States are interpretable without returns |
| 9-10 | Freeze and run the ETF payoff atlas | Every state and ETF group is reported |
| 11 | Compare regime information with frozen MOM60 | Same universe, dates, costs, and eligibility |
| 12 | Publish Research Note 02 and a stop/continue decision | Claims match evidence and limitations |

## Research Note Plan

1. PBOC Policy Narratives and ETF Returns: A Qualified Negative Result.
2. China Macro Regimes and ETF Group Payoffs.
3. Does Regime Information Improve a Frozen MOM60 Allocation?
4. Scheduled PBOC Events and Cross-Asset Repricing.
5. ETF Availability, Suspensions, and Backtest Bias in China.
6. Risk Attribution of a Regime-Aware ETF Portfolio, only if a strategy passes.

## Stop Conditions

- Stop a study when its frozen evidence threshold fails; preserve the negative
  result instead of changing the feature or horizon.
- Do not create a strategy from a descriptive atlas.
- Do not add machine learning until an interpretable baseline leaves a concrete
  residual problem.
- Do not start Study 03 before Study 02 has a reproducible research note.
- Do not optimize the number of GitHub projects or reports at the expense of a
  defensible question, data contract, benchmark, and conclusion.
