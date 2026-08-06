# Narrative-Regime ETF Allocation

[![CI](https://github.com/luka77bie/Quant-Research/actions/workflows/ci.yml/badge.svg)](https://github.com/luka77bie/Quant-Research/actions/workflows/ci.yml)

Status: data reliability milestone. Strategy results have not yet been
generated in this repository.

This project studies a narrower follow-up question to
[`narrative-aware-etf-rotation`](https://github.com/luka77bie/narrative-aware-etf-rotation):

> Under which macro, uncertainty, and liquidity regimes does narrative
> information add incremental value to a frozen ETF momentum baseline?

The first milestone is data reliability. Market-data requests are resumable,
cached per provider and symbol, and recorded in an append-only provenance
manifest. One failed symbol does not invalidate a complete batch, and a
provider that returns only part of the requested history is never silently
treated as complete.

## Current scope

- Chinese broad-market, sector, style, bond, commodity, and overseas ETFs.
- Daily adjusted OHLCV data.
- AKShare as the default source; Yahoo Finance as an optional fallback.
- A frozen MOM60 monthly Top-3 baseline before narrative features are added.
- Research outputs only; no automatic trading or investment advice.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[akshare,yahoo,dev]'
```

## Download market data

```bash
nrea download \
  --universe configs/etf_universe.csv \
  --start 2018-01-01 \
  --end 2026-07-31 \
  --providers akshare,yahoo
```

The command prints a per-symbol summary and returns a non-zero exit code when
every provider fails or returns incomplete coverage for one or more symbols.
Successfully downloaded symbols remain cached and are skipped on the next
identical run. Incomplete provider responses are preserved for diagnosis while
the downloader tries the next provider. Use `--refresh` to request all symbols
again.

After three consecutive incomplete symbols, the default batch circuit breaker
marks the unrequested remainder as `skipped`. This prevents a provider-wide
outage from triggering requests for the entire universe. Rerun the same command
later to resume; use `--max-consecutive-failures 0` only when deliberately
disabling the breaker.

Generated local artifacts:

```text
data/raw/<provider>/<symbol>.csv
data/raw/<provider>/<symbol>.meta.json
data/manifests/downloads.jsonl
data/manifests/latest_download_summary.csv
```

`downloads.jsonl` records each provider attempt as well as the final status for
each symbol. `latest_download_summary.csv` is the short operational checklist:
only rows marked `downloaded` or `cached` are research-ready.

Audit a provider cache without making any network request:

```bash
nrea audit \
  --universe configs/etf_universe.csv \
  --provider akshare
```

The audit re-reads every cached file and checks its checksum, metadata, row
count, observed boundaries, OHLC validity, and coverage. It exits unsuccessfully
unless every requested symbol is marked `ready`.

If an ETF was listed after the requested research start, enter its verified
first available date in the universe file's `available_from` column. Until
then, the downloader intentionally reports the shorter history as `partial`.
This prevents launch-date truncation from being silently confused with full
coverage.

See [`research/data_source_policy.md`](research/data_source_policy.md) for
retry, fallback, and cross-provider rules.
The dated live probe and its observed rate-limit failures are recorded in
[`research/provider_probe_report.md`](research/provider_probe_report.md).

## Frozen baseline

The baseline command accepts a long-form adjusted-close file with `date`,
`symbol`, and `close` columns:

```bash
nrea baseline \
  --prices data/processed/common_sample.csv \
  --output-dir artifacts/mom60
```

It writes daily returns, dated Top-3 selections, and summary metrics. Signals
use 60 trading observations and the last panel date in each month. Weights
become active on the next panel date, drift between rebalances, and incur 10
basis points times one-way turnover. Missing returns for held ETFs stop the run.
The exact execution approximation and its limitation are frozen in
[`research/research_contract.md`](research/research_contract.md) and
[`research/decision_log.md`](research/decision_log.md).

## Quality checks

```bash
python3 -m pytest
ruff check .
```

CI runs the offline suite on Python 3.10 and 3.12. It does not call AKShare,
Yahoo Finance, or any live market-data endpoint.

## Research status

The repository currently establishes research contracts, provider isolation,
resumable downloads, cache audits, coverage validation, provenance manifests,
and an offline-tested MOM60 baseline engine. The next gate is to verify ETF
availability dates and run that baseline on a fully audited common sample. No
narrative model is eligible for implementation before that gate passes.

## License

MIT. Research outputs are educational and do not constitute investment advice.
