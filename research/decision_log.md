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
