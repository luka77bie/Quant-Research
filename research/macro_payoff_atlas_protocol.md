# Study 02 ETF Payoff Atlas Protocol

## Status

Protocol v2, frozen before reading any ETF return or payoff result.

## Question

Do existing liquid ETF asset groups have meaningfully different forward returns
across the already frozen single-dimension growth, inflation, and liquidity
states?

This is a descriptive payoff atlas. It is not an allocation strategy and does
not test combined regimes.

## Market sample

- Use the existing 18-ETF universe and its six committed asset groups.
- Use market observations from 1 January 2018 through 31 July 2026 so the
  December 2025 macro release retains its full 60-session forward endpoint.
- Respect each ETF's verified listing date and explicit no-trade exceptions.
- Use `510300` as the reference trading calendar.
- Require both activation and horizon endpoints to be tradable.
- Use adjusted close-to-close total returns.
- Equal-weight available ETF returns within each asset group and event.

## Timing

Only macro rows with all three source families ready are eligible. Add 24 hours
to `panel_available_after`, then use the first `510300` close at or after that
timestamp. This deliberately avoids assuming execution immediately after an
official release. Forward endpoints are 5, 20, and 60 reference sessions after
activation; 20 sessions is primary.

## Frozen comparisons

| Dimension | First state | Second state |
| --- | --- | --- |
| Growth | Contraction | Expansion |
| Inflation | Falling | Rising |
| Liquidity | Decelerating | Accelerating |

The reported difference is second state minus first state. Neutral and stable
states remain in the chronology but are excluded because they failed the frozen
eight-observation gate. Thresholds are not changed.

## Statistics

Every dimension, asset-group, and horizon cell reports observations, independent
state episodes, mean, median, standard deviation, and positive-return rate. The
state difference uses an OLS indicator with Newey-West covariance and maximum
lag equal to the ceiling of horizon sessions divided by 20.

A comparison is eligible only when each state has at least eight observations
and five episodes. All dimension-group-window p-values form one
Benjamini-Hochberg family with a 10% reference FDR. No winsorization or selective
horizon reporting is allowed.

## Claims and stop rules

- Current official pages support only a publication-time reconstruction, not a
  strict historical-vintage claim.
- No combined state, portfolio, or MOM60 overlay may be built in this stage.
- Stop if the market common sample fails its existing audit.
- Mark individual comparisons ineligible when either state misses its count or
  episode gate.
- Stop before strategy construction if no 20-session comparison survives the
  frozen multiplicity rule.
- Even a surviving descriptive comparison requires a separately frozen MOM60
  comparison and allocation rule.

## Pre-outcome amendment

Protocol v1 omitted the market sample end. Implementation review showed that a
31 December 2025 market cutoff would censor the late-2025 macro observations,
because their releases and 60-session endpoints occur in 2026. Before computing
any ETF return, v2 freezes 31 July 2026 as the endpoint already used by the
project's qualified market sample. No dimension, state, horizon, estimator, or
reporting threshold changed.
