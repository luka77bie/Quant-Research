# Market Data Source Policy v0.1

## Operating rule

Network and provider failures are expected operational states, not exceptional
research events. A batch must preserve completed symbols, expose incomplete
symbols, and be safe to rerun.

## Provider order

1. Tencent's adjusted K-line endpoint is the primary convenience source for
   Chinese ETF history and is requested in calendar-year chunks.
2. AKShare is an optional per-symbol fallback kept in an isolated cache.
3. Yahoo Finance is an explicit optional fallback, not a required queue.
4. A fallback timeout or throttle must not erase another provider's cache or
   block later symbols from being attempted.

## Retry and resume

- Each provider receives three attempts by default.
- Retries use exponential backoff with small jitter.
- Symbols are processed sequentially with a configurable delay.
- Tencent history is paged by calendar year to stay well below the endpoint's
  row cap; repeated refreshes merge by date instead of replacing good rows.
- Validated caches are skipped on an identical rerun.
- Failed and partial symbols are attempted again.
- Three consecutive incomplete symbols stop the batch by default. Remaining
  symbols are recorded as `skipped` and resume on a later run.
- Every attempt and final symbol result is appended to `downloads.jsonl`.

## Completeness gate

A provider response is `validated` only when:

- required OHLCV columns are present and numerically valid;
- OHLC relationships are internally consistent;
- observed boundaries are within seven calendar days of expected boundaries;
- no internal calendar gap exceeds fourteen days;
- the cache checksum still matches its metadata.

ETF launch dates must be verified separately and recorded as `available_from`.
The tolerance rules are screening checks, not proof that every exchange trading
day is present. The reference-calendar audit is required before backtesting.
Only a dual-source verified no-trade date in the committed exception ledger may
receive an explicit prior-close mark with zero volume and `is_tradable=false`.

## Cross-provider boundary

Provider caches remain separate. Do not automatically fill AKShare gaps with
Yahoo rows. Before any cross-provider merge, compare an overlapping period for:

- date coverage;
- adjusted-close return differences;
- volume units;
- corporate-action dates;
- timezone and trading-date alignment.

The comparison and merge decision must be recorded in the decision log.

Sina's raw ETF history is used only as independent coverage evidence. Its
adjustment payload contains transient records around some ETF share splits and
is not an approved backtest source.
