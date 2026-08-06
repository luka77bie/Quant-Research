# Market Data Source Policy v0.1

## Operating rule

Network and provider failures are expected operational states, not exceptional
research events. A batch must preserve completed symbols, expose incomplete
symbols, and be safe to rerun.

## Provider order

1. AKShare is the primary convenience source for Chinese ETF history.
2. Yahoo Finance is an optional per-symbol fallback, not a required queue.
3. A Yahoo timeout or throttle must not erase an AKShare cache or block later
   symbols from being attempted.

## Retry and resume

- Each provider receives three attempts by default.
- Retries use exponential backoff with small jitter.
- Symbols are processed sequentially with a configurable delay.
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
day is present. A later exchange-calendar audit is required before backtesting.

## Cross-provider boundary

Provider caches remain separate. Do not automatically fill AKShare gaps with
Yahoo rows. Before any cross-provider merge, compare an overlapping period for:

- date coverage;
- adjusted-close return differences;
- volume units;
- corporate-action dates;
- timezone and trading-date alignment.

The comparison and merge decision must be recorded in the decision log.

Sina's unadjusted ETF history is not a substitute for the frozen adjusted-close
series. Its current adjustment payload must not be used until the factor and
cash-adjustment formula is verified against documented corporate-action cases.
