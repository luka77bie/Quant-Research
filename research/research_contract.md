# Research Contract v0.1

## Question

Under which macro, uncertainty, and liquidity regimes does point-in-time
narrative information add incremental value to a frozen Chinese ETF momentum
rotation baseline?

## Prior evidence

The predecessor project selected MOM60 monthly Top-3 as its primary model.
Its market-attention proxy showed defensive behaviour in 2022-2023 but did not
improve aggregate walk-forward out-of-sample performance. This is motivating
evidence, not proof that a conditional narrative model will work.

## Frozen baseline

- Signal: 60-trading-day adjusted-close momentum.
- Selection: cross-sectional Top-3 among eligible ETFs.
- Weighting: equal weight.
- Rebalance: monthly.
- Execution: target weights become active on the next common panel date. The
  close-to-close return on that date is used as a documented daily-data
  approximation to next-session execution.
- Costs: 10 basis points multiplied by one-way turnover.
- Eligibility: official listing date has passed and 60 valid observations are
  available on the common reference calendar.
- Calendar: `510300` defines panel trading dates; another ETF enters only after
  its listing date. An unverified missing session blocks the sample. A committed
  dual-source no-trade exception receives an explicit non-tradable prior-close
  mark and zero volume.

Baseline definitions may only change to fix a documented correctness bug.

## Evidence gates

1. Data requests and source versions must be traceable through manifests.
2. A symbol failure must be visible and must not be silently filled.
3. Narrative records must expose `published_at`, `retrieved_at`, and
   `available_at` before entering a historical signal.
   Exact source domain, timestamp evidence, document checksum, revision risk,
   and point-in-time verification status must also remain auditable.
4. Model selection and final evaluation periods must be separated.
5. Results must include turnover, drawdown, subperiods, and failure cases.

## Initial stop conditions

- No reproducible point-in-time narrative archive can be assembled.
- Results depend on one crisis subperiod or one ETF family.
- Incremental performance disappears under reasonable costs or signal delays.
- More than two consecutive project weeks are spent on provider-specific data
  plumbing without producing an auditable common sample.
- The combined model cannot beat or explain differences from frozen MOM60 in
  walk-forward evaluation.
