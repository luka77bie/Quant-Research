# Decision Log

## 2026-08-06: Start a new repository

The predecessor remains an immutable reference and baseline. This repository
starts clean to avoid carrying forward script sprawl and research decisions
made after observing historical results.

## 2026-08-06: Make downloads resumable

AKShare requests may fail for only part of a symbol universe, while Yahoo
Finance can throttle or queue requests. Data is therefore cached per provider
and symbol. Each attempt is recorded independently, and reruns preserve prior
successes.

## 2026-08-06: Keep providers optional

Core tests do not import or call external data services. Provider packages are
optional dependencies, and network behaviour is tested through deterministic
fake providers.

## 2026-08-06: Preserve partial data but fail the research gate

A non-empty provider response is not automatically complete. Actual date
coverage and long internal gaps are checked. Partial caches are retained so a
rerun can extend them, but the command exits unsuccessfully until every symbol
has a complete provider result or an explicit availability boundary.

## 2026-08-06: Do not splice providers automatically

AKShare forward-adjusted prices and Yahoo auto-adjusted prices may encode
corporate actions differently. Each provider keeps an independent cache.
Cross-provider history can only be combined after a documented overlap audit.

## 2026-08-06: Freeze the daily execution approximation

MOM60 signals use the final observed close in each calendar month. New target
weights become active on the next common panel date, and that date's
close-to-close return is attributed to the new portfolio. This is a deliberate
daily-data approximation, not a claim of exact next-open execution. It remains
fixed across all benchmark comparisons; an open-aware sensitivity run is
required before any investability claim.

Portfolio weights drift with asset returns between monthly rebalances. Costs
are 10 basis points times one-way turnover, including the initial move from
cash. Missing returns for held assets stop the run instead of being treated as
zero.

## 2026-08-06: Use official listing dates and a reference calendar

ETF eligibility begins on the official secondary-market listing date recorded
in the source ledger. The common sample uses `510300` trading dates as its
reference calendar. Each ETF is checked only from the later of the research
start and its own listing date. Missing or non-reference observations block the
sample unless a later committed decision explicitly qualifies a no-trade date.

## 2026-08-06: Qualify Tencent and mark verified no-trade dates

Tencent adjusted ETF history replaces Eastmoney as the default convenience
source after a full-history `510300` overlap showed identical dates, return
correlation above 0.999999, and matching volume units. Requests use calendar-year
chunks and remain isolated by provider.

Eight eligible symbol-dates are absent from both Tencent and Sina histories.
They are committed in `configs/etf_calendar_exceptions.csv`. The panel records
each at the prior close with zero volume, `observation_status=verified_no_trade`,
and `is_tradable=false`. Any unlisted missing date still blocks the sample.

## 2026-08-06: Accept MOM60 as the qualified benchmark

The frozen MOM60 run on the Tencent common sample is accepted as the benchmark,
not as a successful strategy claim. At 10 basis points it annualizes at 9.68%
with a 0.486 zero-rate Sharpe and -42.02% maximum drawdown. The result is highly
path-dependent, including 103.99% in 2020 and -32.39% in 2022. The next gate is
reproduction of the predecessor market-attention proxy on the same panel.
