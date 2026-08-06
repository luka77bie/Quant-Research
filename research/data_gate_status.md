# Data Gate Status: 2026-08-06

## Passed

- Official secondary-market listing dates are verified for all 18 ETFs.
- Tencent produced 18 validated, provider-isolated caches from 2018-01-01
  through 2026-07-31 using calendar-year requests.
- The strict `510300` reference-calendar audit passed for all 18 ETFs.
- Eight dual-source verified no-trade dates are explicit in the exception
  ledger and sample; there are no unverified missing dates.
- The qualified common sample contains 35,372 rows and 18 symbols.
- No selected asset is assumed tradable on a marked no-trade execution date.

## Previous Provider Failure

Eastmoney completed `510300` but then repeatedly closed connections for other
symbols. Yahoo was rate-limited. Both remain isolated optional fallbacks; neither
is required for the qualified sample.

BaoStock was also tested because it requires no token. It recognized ETF basic
information but returned zero K-line rows for `510300` under unadjusted, forward-
adjusted, and backward-adjusted requests, so it was rejected.

## Next Gate

The frozen MOM60 baseline is now runnable. Narrative and regime features remain
ineligible until a point-in-time archive exposes `published_at`, `retrieved_at`,
and `available_at` and passes the research contract.
