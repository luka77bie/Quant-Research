# Study 02 Return-Blind Macro Panel

## Decision

Pass the macro panel gate. Freeze the ETF payoff-atlas protocol before joining
any market outcome.

## Frozen construction

- Growth: manufacturing PMI below, equal to, or above 50.
- Inflation: falling, stable, or rising three-month change in CPI YoY.
- Liquidity: decelerating, stable, or accelerating three-month change in M2 YoY.
- Minute-level releases become available at the reported timestamp.
- Date-only releases become available at the next Beijing midnight.
- A monthly row becomes available only after the latest of its three releases.
- Missing data are never filled; combined states are not constructed.

These rules were frozen without ETF prices or returns. The machine-readable
contract is `configs/macro_regime_protocol.json`.

## Coverage

The panel covers 96 months from January 2018 through December 2025. Ninety-five
months have all three article-ready releases. January 2025 is incomplete because
the national M2 source is missing.

| Dimension | Primary state | Months | Episodes | Longest episode |
| --- | --- | ---: | ---: | ---: |
| Growth | Contraction | 43 | 11 | 8 |
| Growth | Expansion | 50 | 13 | 18 |
| Inflation | Falling | 42 | 13 | 7 |
| Inflation | Rising | 46 | 11 | 12 |
| Liquidity | Decelerating | 47 | 12 | 17 |
| Liquidity | Accelerating | 41 | 15 | 12 |

State counts use the 95-month common sample where all three source families are
ready. The primary states all exceed the frozen eight-month threshold and occur
in at least 11 separate episodes. Exact neutral or stable observations number only
two to four months. They remain visible in the chronology but are not eligible
for separate payoff claims.

## Interpretation and limits

The chronology is economically interpretable and persistent without being
dominated by one contiguous episode. It is still a current-page
publication-time reconstruction, not a strict historical-vintage panel. A
three-month change also creates expected warm-up gaps and propagates the
January 2025 M2 gap into its corresponding change comparison; these are not
silently filled.

No combined 27-cell regime, clustering model, ETF return, or portfolio rule was
created. The next artifact must pre-register ETF groups, forward horizons,
execution timing, costs, minimum observations, multiplicity handling, and the
comparison with the frozen MOM60 baseline.
