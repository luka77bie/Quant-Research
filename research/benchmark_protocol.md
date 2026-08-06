# Benchmark Protocol v0.1

## Claim-result contract

| Claim | Required evidence | Failure condition |
| --- | --- | --- |
| Narrative adds incremental value | Walk-forward combined model versus frozen MOM60 and macro-only baseline | Improvement disappears OOS or after reasonable costs and delays |
| Value is regime-conditioned | Pre-specified regime attribution and interaction ablation | Result depends on one hand-labelled crisis period |
| Result is not another price proxy | Price/volume controls, lagged labels, and shuffled-label placebo | Narrative signal contribution vanishes after controls |
| Pipeline is reproducible | Data, config, commit, command, and artifact ledger | Headline result cannot be traced to raw inputs |

## Frozen evaluation rules

- Model selection and final evaluation periods remain separate.
- No parameter is selected using the final evaluation window.
- Failed symbols and coverage differences are reported for every run.
- Baselines use the same eligible universe, costs, dates, and execution delay.
- Eligibility is dynamic from official ETF listing dates; no pre-listing return
  is filled or inferred.
- Headline runs require every eligible ETF to align to the committed reference
  calendar without a missing held-session assumption.
- Excluded ETFs and dates require a pre-specified, logged reason.
- Strong superiority claims require uncertainty estimates, not a single Sharpe
  ratio comparison.

## Required ablations

1. MOM60 only.
2. MOM60 plus macro regime.
3. MOM60 plus narrative signal.
4. MOM60 plus macro and narrative interaction.
5. Combined model with shuffled narrative labels.
6. Combined model with additional publication and execution delays.
