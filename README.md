# Luka Quant Research Lab

[![CI](https://github.com/luka77bie/Quant-Research/actions/workflows/ci.yml/badge.svg)](https://github.com/luka77bie/Quant-Research/actions/workflows/ci.yml)

Personal systematic strategy research focused on Chinese policy, macro regimes,
and liquid ETF allocation.

Status: Study 01 is complete as a qualified negative result. Study 02 has passed
its official-release, current-page evidence, and cross-year template gates;
its 2018-2025 source catalog, full article validation, and return-blind macro
panel gates now pass. The next stage freezes the ETF payoff-atlas protocol.
Strict historical-version verification remains open.

## Research identity

This is not a collection of trading scripts or a claim to compete with an
institutional quant platform. It is a public strategy-research portfolio built
around one repeatable process:

> Economic question -> falsifiable hypothesis -> auditable data -> frozen
> benchmark -> complete sensitivity grid -> decision, including stopping.

The lab is positioned for strategy research, systematic investing, ETF and
multi-asset research, and securities proprietary-investment roles. Engineering
exists to make the research reproducible; it is not the research contribution
by itself.

## Research portfolio

| Study | Question | Status | Main decision |
| --- | --- | --- | --- |
| 01 Narrative-Regime ETF Allocation | Does PBOC policy language add information beyond ETF momentum and market controls? | Complete, exploratory | No adjusted candidate; do not construct a narrative portfolio |
| 02 China Macro Regime ETF Atlas | How do liquid ETF groups behave across pre-defined growth, inflation, and liquidity states? | Return-blind panel passed | Freeze the payoff-atlas protocol before reading ETF outcomes |
| 03 Policy Event Research | Which scheduled policy events create repeatable cross-asset repricing after realistic delays? | Planned | Start only after Study 02 passes its data gate |

See [`lab/roadmap_v1_1.md`](lab/roadmap_v1_1.md) for scope and sequencing,
[`lab/research_process.md`](lab/research_process.md) for the common workflow,
and [`research_notes/01_policy_narrative_etf_relations.md`](research_notes/01_policy_narrative_etf_relations.md)
for the interview-length note from Study 01.

Run the Study 02 return-blind release-record pilot:

```bash
nrea macro-release-pilot \
  --catalog configs/macro_release_pilot.csv \
  --output-dir outputs/macro_release_pilot
```

The pilot audits four manufacturing PMI, four CPI YoY, and four M2 YoY release
records without reading ETF returns. It distinguishes original release pages,
official retrospective confirmation, revision notes, and historical-snapshot
status. The current result is documented in
[`research/macro_release_pilot_report.md`](research/macro_release_pilot_report.md).

Archive and audit the registered official-page evidence:

```bash
nrea macro-evidence-fetch \
  --catalog configs/macro_release_pilot.csv \
  --evidence configs/macro_release_evidence.csv \
  --root .

nrea macro-evidence-audit \
  --catalog configs/macro_release_pilot.csv \
  --evidence configs/macro_release_evidence.csv \
  --root . \
  --output-dir outputs/macro_evidence
```

The committed evidence ledger locks page checksums and exact visible-text
fragments for release timing and values. Cached HTML remains local under
`data/raw/macro_release_pages/`.

Audit one deterministic parser per source family across three anchor years:

```bash
nrea macro-template-audit \
  --catalog configs/macro_template_drift_catalog.csv \
  --root . \
  --output-dir outputs/macro_template_drift
```

Enumerate the official source indexes and audit monthly coverage without market
outcomes:

```bash
nrea macro-catalog-discovery \
  --start 2018-01 \
  --end 2025-12 \
  --output-dir outputs/macro_catalog_discovery
```

The index-only pass discovered 53/96 NBS PMI, 53/96 NBS CPI, and 95/96 PBOC M2
records. Exact-title official search backfills 72 NBS records; 14 reviewed
official candidates complete both NBS families pending article validation.
The full article audit now verifies all 287 available pages: 96/96 PMI, 96/96
CPI, and 95/96 M2. January 2025 national M2 remains explicitly missing. See
`research/macro_article_validation_report.md` for the result and limitations.

Reproduce the exact-title backfill and apply the reviewed residual candidates:

```bash
nrea macro-catalog-backfill \
  --catalog outputs/macro_catalog_discovery/macro_monthly_source_catalog.csv \
  --output-dir outputs/macro_catalog_backfill

nrea macro-catalog-apply-seeds \
  --catalog outputs/macro_catalog_backfill/macro_monthly_source_catalog_backfilled.csv \
  --seeds configs/macro_catalog_backfill_seeds.csv \
  --output-dir outputs/macro_catalog_seeded
```

Cache and validate every available monthly article before defining any regime:

```bash
nrea macro-catalog-fetch \
  --catalog configs/macro_monthly_source_catalog.csv \
  --root . \
  --output-dir outputs/macro_article_validation

nrea macro-catalog-validate \
  --catalog configs/macro_monthly_source_catalog.csv \
  --root . \
  --output-dir outputs/macro_article_validation
```

The fetch is resumable per record and leaves the one missing national M2 month
explicit. Use `--record-ids` to retry only failed records. The offline audit
checks the official URL, catalog title, statistical period, release timing, and
headline value. PMI, CPI, and M2 must each reach 95% article-ready coverage;
otherwise Study 02 remains blocked and no ETF returns or regime thresholds are
used.

Build the frozen return-blind macro panel from the committed evidence ledger:

```bash
nrea macro-panel \
  --ledger configs/macro_article_evidence_ledger.csv \
  --protocol configs/macro_regime_protocol.json \
  --output-dir outputs/macro_panel
```

The protocol uses PMI relative to 50 for growth and three-month changes in CPI
YoY and M2 YoY for inflation and liquidity direction. It does not fill missing
data or create combined states. The current panel has 95 complete months and
passes the minimum eight-observation gate for two economically meaningful
states in every dimension. See `research/macro_panel_report.md`.

## Study 01: Narrative-Regime ETF Allocation

The flagship study is a narrower follow-up to
[`narrative-aware-etf-rotation`](https://github.com/luka77bie/narrative-aware-etf-rotation):

> Under which macro, uncertainty, and liquidity regimes does narrative
> information add incremental value to a frozen ETF momentum baseline?

Study 01 evaluates whether the narrative leg is reliable enough to justify that
conditional model. It is not a completed test of macro-regime interactions: the
narrative evidence failed its pre-model gate, so the project stopped before
fitting a flexible conditional strategy. Study 02 now builds the macro-regime
leg independently and return-blind.

Study 01 now spans provider qualification, a frozen baseline, official-policy
archive construction, return-blind text diagnostics, timing protocols,
unadjusted falsification, and adjusted inference. Market-data requests remain
resumable and cached per provider and symbol. One failed symbol does not
invalidate a complete batch, and a partial history is never silently treated as
complete.

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

Download the reviewed official-policy quarterly catalog:

```bash
nrea narrative-fetch \
  --catalog configs/pboc_mpr_catalog.csv \
  --sources configs/narrative_sources.csv
```

Audit local checksums, three required timestamps, historical snapshot status,
and quarterly coverage without a network request:

```bash
nrea narrative-audit \
  --catalog configs/pboc_mpr_catalog.csv \
  --sources configs/narrative_sources.csv \
  --output-dir outputs/narrative_archive_full
```

Extract deterministic PDF text and run extraction quality checks:

```bash
nrea narrative-extract \
  --catalog configs/pboc_mpr_catalog.csv \
  --sources configs/narrative_sources.csv \
  --output-dir outputs/narrative_text_full
```

Parse and audit the forward-looking policy section:

```bash
nrea narrative-sections \
  --catalog configs/pboc_mpr_catalog.csv \
  --sources configs/narrative_sources.csv \
  --output-dir outputs/narrative_sections_full
```

Build the frozen return-blind policy-language diagnostics:

```bash
nrea narrative-features \
  --catalog configs/pboc_mpr_catalog.csv \
  --sources configs/narrative_sources.csv \
  --lexicon configs/policy_term_lexicon.csv \
  --output-dir outputs/policy_features
```

Freeze and audit the three market-session timing protocols:

```bash
nrea narrative-timing \
  --features outputs/policy_features/policy_features.csv \
  --prices data/processed/common_sample_tencent/common_sample.csv \
  --reference-symbol 510300 \
  --output-dir outputs/narrative_timing
```

Audit all frozen numeric features before reading market relationships:

```bash
nrea narrative-diagnostics \
  --features outputs/policy_features/policy_features.csv \
  --output-dir outputs/policy_feature_diagnostics
```

Execute every frozen feature, delay, horizon, and ETF combination without
constructing a portfolio:

```bash
nrea market-relations \
  --features outputs/policy_features/policy_features.csv \
  --schedule outputs/narrative_timing/narrative_activation_schedule.csv \
  --prices data/processed/common_sample_tencent/common_sample.csv \
  --universe configs/etf_universe.csv \
  --protocol configs/market_relation_protocol.json \
  --reference-symbol 510300 \
  --output-dir outputs/descriptive_market_relations
```

This command audits all 5,184 planned symbol-window combinations, writes every
exclusion reason, attaches controls available by the previous reference-session
close, and reports unadjusted Pearson and Spearman relationships. It does not
run inference, select a specification, or simulate a strategy. See
[`research/descriptive_market_relation_report.md`](research/descriptive_market_relation_report.md).

Run the separately frozen post-descriptive adjustment grid:

```bash
nrea adjusted-relations \
  --panel outputs/descriptive_market_relations/market_relation_panel.csv \
  --protocol configs/adjusted_relation_protocol.json \
  --output-dir outputs/adjusted_market_relations
```

The primary model controls for text length, lagged MOM60, lagged volatility, and
asset-group fixed effects, with report-event clustered uncertainty and
Benjamini-Hochberg correction across all 99 specifications. The implementation
also reports 594 descriptive asset-group coefficients and 99 adjusted
dispersion models. See
[`research/adjusted_relation_report.md`](research/adjusted_relation_report.md).

The downloader caches each PDF independently, retries failures, rejects
unapproved domains and non-PDF responses, and locks reviewed checksums in the
catalog. All 32 quarterly documents from 2018 through 2025 are archived and
extract cleanly, and the policy-section parser passes for 32 of 32 reports. All
remain provisional because no matching contemporaneous snapshot has been
established, so the strict modeling audit intentionally exits unsuccessfully.
The evidence, permitted exploratory use, and stop rules are in
[`research/pboc_archive_and_text_report.md`](research/pboc_archive_and_text_report.md).

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
universe. The PBOC archive covers all 32 quarters and deterministic extraction
and policy-section parsing pass, but none of the documents has a historically
matched snapshot. Strict point-in-time modeling remains blocked;
publication-time text diagnostics may proceed only under the qualified
exploratory protocol. The frozen diagnostics use no return data and create no
composite score. The 24-hour, 48-hour, and next-month session joins pass with no
lookahead violations. Feature stability diagnostics pass with only expected
first-observation missingness; redundant representations remain audit-only. The
descriptive relationship audit covers every frozen combination with zero
control-date violations, but most primary-feature signs are not stable across
delay and horizon choices. After fixed controls and multiplicity correction,
zero pooled or dispersion specifications meet the frozen 10% FDR threshold.
Strategy construction remains stopped.

## License

MIT. Research outputs are educational and do not constitute investment advice.
