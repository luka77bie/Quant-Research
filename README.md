# Narrative-Regime ETF Allocation

[![CI](https://github.com/luka77bie/Quant-Research/actions/workflows/ci.yml/badge.svg)](https://github.com/luka77bie/Quant-Research/actions/workflows/ci.yml)

Status: qualified market-data panel, frozen MOM60 baseline, and completed
market-attention control reproduction.

This project studies a narrower follow-up question to
[`narrative-aware-etf-rotation`](https://github.com/luka77bie/narrative-aware-etf-rotation):

> Under which macro, uncertainty, and liquidity regimes does narrative
> information add incremental value to a frozen ETF momentum baseline?

The current milestone is data qualification. Market-data requests are resumable,
cached per provider and symbol, and recorded in an append-only provenance
manifest. One failed symbol does not invalidate a complete batch, and a
provider that returns only part of the requested history is never silently
treated as complete.

## Current scope

- Chinese broad-market, sector, style, bond, commodity, and overseas ETFs.
- Daily adjusted OHLCV data.
- Tencent adjusted K-line history as the default source; AKShare and Yahoo
  Finance as optional fallbacks.
- A frozen MOM60 monthly Top-3 baseline before narrative features are added.
- Research outputs only; no automatic trading or investment advice.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[akshare,dev]'
```

## Download market data

```bash
nrea download \
  --universe configs/etf_universe.csv \
  --start 2018-01-01 \
  --end 2026-07-31 \
  --providers tencent,akshare
```

The command prints a per-symbol summary and returns a non-zero exit code when
every provider fails or returns incomplete coverage for one or more symbols.
Successfully downloaded symbols remain cached and are skipped on the next
identical run. Incomplete provider responses are preserved for diagnosis while
the downloader tries the next provider. Use `--refresh` to request all symbols
again.

Resume only selected symbols after a provider cooldown without editing the
universe file:

```bash
nrea download \
  --universe configs/etf_universe.csv \
  --symbols 510500,512100 \
  --start 2018-01-01 \
  --end 2026-07-31 \
  --providers tencent \
  --delay 10
```

Unknown or duplicate values passed to `--symbols` stop before any network
request. Selected symbols retain the universe file's deterministic order.

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
  --provider tencent
```

The audit re-reads every cached file and checks its checksum, metadata, row
count, observed boundaries, OHLC validity, and coverage. It exits unsuccessfully
unless every requested symbol is marked `ready`.

Official listing dates are committed in `configs/etf_availability_sources.csv`
and mirrored into the universe file's `available_from` column. The downloader
uses those dates for post-2018 listings instead of incorrectly treating their
pre-listing period as missing history.

Build a dynamic-universe sample only after every provider cache is ready:

```bash
nrea build-sample \
  --universe configs/etf_universe.csv \
  --availability-sources configs/etf_availability_sources.csv \
  --calendar-exceptions configs/etf_calendar_exceptions.csv \
  --provider tencent \
  --start 2018-01-01 \
  --end 2026-07-31 \
  --reference-symbol 510300 \
  --output-dir data/processed/common_sample
```

This command checks the configured dates against their source ledger and aligns
each ETF, after its own listing date, to `510300` trading sessions. Unverified
missing or extra sessions block `common_sample.csv`. A dual-source verified
no-trade date receives an explicit zero-volume, non-tradable mark at the prior
close; it is never silently filled.

Compare isolated provider caches before approving a fallback source:

```bash
nrea compare-providers \
  --left-provider akshare \
  --right-provider tencent \
  --symbols 510300 \
  --output data/manifests/akshare_tencent_comparison.csv
```

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
  --output-dir outputs/mom60
```

It writes daily returns, dated Top-3 selections, and summary metrics. Signals
use 60 trading observations and the last panel date in each month. Weights
become active on the next panel date, drift between rebalances, and incur 10
basis points times one-way turnover. Missing returns for held ETFs stop the run.
The exact execution approximation and its limitation are frozen in
[`research/research_contract.md`](research/research_contract.md) and
[`research/decision_log.md`](research/decision_log.md).
The qualified result, annual path, and 10/20/30 bps sensitivity are reported in
[`research/mom60_baseline_report.md`](research/mom60_baseline_report.md).

## Market-attention control

Reproduce the predecessor project's fixed market-attention composite without a
weight search:

```bash
nrea attention-reproduction \
  --prices data/processed/common_sample.csv \
  --output-dir outputs/attention_reproduction
```

The command writes both strategy paths, selections, full signal history,
subperiod comparisons, metrics, and a checksum manifest. Tencent does not
provide transaction value, so the command records whether activity value came
from a reported amount, `close * volume`, or an explicit verified no-trade zero.

The 2022-2023 defensive direction reproduced, but full-sample drawdown worsened
and behavior was period-sensitive. This feature is therefore frozen as a
market-data control, not accepted as narrative evidence. See
[`research/attention_proxy_reproduction.md`](research/attention_proxy_reproduction.md).

## Narrative archive gate

Download only the manually reviewed official-policy pilot catalog:

```bash
nrea narrative-fetch \
  --catalog configs/narrative_pilot_catalog.csv \
  --sources configs/narrative_sources.csv
```

Audit local checksums, three required timestamps, historical snapshot status,
and quarterly coverage without a network request:

```bash
nrea narrative-audit \
  --catalog configs/narrative_pilot_catalog.csv \
  --sources configs/narrative_sources.csv \
  --output-dir outputs/narrative_archive_pilot
```

The pilot downloader caches each PDF independently, retries failures, rejects
unapproved domains and non-PDF responses, and locks reviewed checksums in the
catalog. The audit intentionally exits unsuccessfully while any expected
quarter is missing or provisional. The current 3-of-32 result and stop rules are
documented in
[`research/narrative_archive_pilot.md`](research/narrative_archive_pilot.md).

## Quality checks

```bash
python3 -m pytest
ruff check .
```

CI runs the offline suite on Python 3.10 and 3.12. It does not call AKShare,
Yahoo Finance, or any live market-data endpoint.

## Research status

ETF listing dates are verified against official exchange lists. The Tencent
provider produced all 18 isolated caches, the common-sample audit passed, and
the frozen MOM60 and market-attention control run on the qualified dynamic
universe. The PBOC narrative archive pilot is operational but covers only 3 of
32 quarters and has no historically matched snapshots. Genuine narrative
features remain blocked until the archive passes the research contract.

## License

MIT. Research outputs are educational and do not constitute investment advice.
