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

If an ETF was listed after the requested research start, enter its verified
first available date in the universe file's `available_from` column. Until
then, the downloader intentionally reports the shorter history as `partial`.
This prevents launch-date truncation from being silently confused with full
coverage.

See [`research/data_source_policy.md`](research/data_source_policy.md) for
retry, fallback, and cross-provider rules.

## Quality checks

```bash
python3 -m pytest
ruff check .
```

CI runs the offline suite on Python 3.10 and 3.12. It does not call AKShare,
Yahoo Finance, or any live market-data endpoint.

## Research status

The repository currently establishes research contracts, provider isolation,
resumable downloads, coverage validation, and provenance manifests. The next
milestone is to verify ETF availability dates and reproduce the predecessor's
frozen MOM60 baseline on a fully audited common sample. No narrative model is
eligible for implementation before that milestone passes.

## License

MIT. Research outputs are educational and do not constitute investment advice.
