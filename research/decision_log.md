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

## 2026-08-06: Retain market attention only as a control

The predecessor's fixed 50% market-attention composite directionally reproduces
its defensive 2022-2023 result: annual return improves from -16.62% to -13.14%
and maximum drawdown from -33.35% to -28.61%. It does not establish a stable
mechanism. Pre-2022 performance is worse, full-sample drawdown deepens from
-42.02% to -49.61%, and 2024+ behavior conflicts with the predecessor result.

Tencent lacks transaction value, so `close * volume` replaces the predecessor's
AKShare amount field. The fixed proxy is retained only as a market-data control.
Its feature weights, windows, and 50% blend will not be tuned on this sample.
The next gate is an auditable point-in-time narrative archive.

## 2026-08-06: Separate archive readiness from point-in-time verification

Three official PBOC quarterly reports were retrieved successfully and locked by
checksum. The downloader is resumable per document and records publication,
retrieval, and conservative availability timestamps. Current official PDFs are
not treated as proof that the same bytes existed at historical publication.

The pilot covers 3 of 32 required 2018-2025 quarters and has no matching
historical snapshots. Archive status is ready, point-in-time status is
provisional, and the modeling gate remains blocked. Text extraction, LLM
features, and narrative backtests will not begin until coverage and revision
risk receive an explicit decision.

## 2026-08-06: Complete the catalog and separate extraction from modeling

The official PBOC master index supplies all 32 quarterly monetary policy
execution reports from 2018 Q1 through 2025 Q4. Exact displayed publication
times, a conservative 24-hour availability delay, official URLs, and SHA-256
checksums are locked in `configs/pboc_mpr_catalog.csv`. All documents download
and pass deterministic text extraction quality checks.

Historical byte identity remains unverified for every report. Snapshot-service
requests were inaccessible in the current environment, and current PBOC paths
show evidence of site migration. The project therefore adopts two independent
gates: archive and extraction readiness pass, while the strict point-in-time
modeling gate remains blocked.

Deterministic section parsing and pre-specified policy-language diagnostics may
proceed as exploratory publication-time reconstruction. LLM features, parameter
search, portfolio optimization, and strict historical-performance claims remain
blocked until either matching historical evidence is found or the research
contract is explicitly downgraded with delay sensitivities and qualified claims.

## 2026-08-06: Pass the deterministic policy-section gate

One parser recognizes the two observed official headings, ignores dotted table
of contents entries, and selects the final exact heading when a PDF exposes both
a contents copy and the body heading. It isolates the forward-looking policy
section in all 32 reports, exceeding the pre-specified 30-report threshold.

The parsed sections contain 88,768 non-whitespace characters in total. Individual
sections range from 2,080 to 3,829 characters, CJK ratios range from 90.28% to
91.89%, and no section hashes are duplicated. This passes the structural parser
gate but does not validate semantics, historical byte identity, or predictiveness.

## 2026-08-06: Freeze return-blind policy diagnostics before market joins

A 25-term literal lexicon is frozen across accommodation, restraint, financial
risk control, exchange-rate stability, and structural support. The feature table
contains counts, per-1,000-character densities, quarter-over-quarter changes,
section length, and prior-quarter character-bigram cosine similarity. It does
not read returns, combine categories, optimize weights, or assign policy labels.

The restraint category is sparse, with nonzero counts in only 8 of 32 quarters.
Three frozen terms have zero counts across the sample: `降息`, `防止资金空转`,
and `房住不炒`. They remain in the audit rather than being replaced after
observing the corpus. This baseline is a measurement diagnostic, not an alpha
signal.

## 2026-08-06: Freeze three session-level publication delays

Narrative features are mapped to the audited `510300` reference calendar using
China Standard Time and a 09:30 session open. The primary 24-hour protocol uses
the catalog-derived `available_at`; the 48-hour sensitivity uses publication
plus 48 hours; the next-month sensitivity uses the first reference session in
the calendar month after local `available_at`.

Each protocol activates a report only at the first session open on or after its
effective timestamp. All 96 report-protocol activations and 6,243 daily as-of
rows pass with zero lookahead violations. Twenty of 32 reports share the same
24-hour and 48-hour activation date because non-trading intervals absorb the
extra delay. This protocol is frozen before examining market relationships.

## 2026-08-06: Resolve measurement redundancy before returns

All 19 numeric policy features pass missingness and finite-value checks. The
eight missing observations are exactly the pre-specified first-quarter values
for similarity, novelty, and quarter-over-quarter changes. No feature has zero
variance.

Six pairs have absolute Spearman correlation of at least 0.90. Five are raw
term counts paired with their length-normalized densities. The sixth is the
identity `section_novelty = 1 - prior_section_similarity`. Before reading any
forward return, density measures and similarity are assigned primary roles;
raw counts and novelty remain audit-only. This is measurement de-duplication,
not performance-based feature selection.

The market relationship protocol is frozen at 5, 20, and 60 reference sessions
for all three timing rules. It prohibits choosing a feature, delay, or window
from observed results and prohibits portfolio construction at this stage.

## 2026-08-08: Complete the descriptive market-relation audit

The frozen protocol produces an explicit row for all 5,184 combinations of 32
reports, three timing rules, three forward windows, and 18 ETFs. Of these, 4,874
are usable. The 310 exclusions comprise 270 pre-listing combinations, 36 cases
without 60-session control history, three non-tradable activation endpoints,
and one non-tradable end endpoint. No control ends on or after activation.

All 19 frozen numeric features are reported through per-symbol, equal-weight
asset-group, and cross-sectional-dispersion outcomes. The output contains raw
Pearson and Spearman coefficients only. Lagged MOM60 and 20-session volatility
are attached to the panel but not used to imply an adjusted or causal result.
There is no inference, portfolio, or result-driven specification selection.

Sign stability is limited. Across the 11 primary features, only 27 of 198
symbol-feature groups, 12 of 66 asset-group-feature groups, and 2 of 11
dispersion-feature groups retain one Spearman sign across all nine timing and
horizon specifications. The median absolute asset-group correlation difference
is about 0.028 between the 24- and 48-hour delays, but about 0.115 between the
24-hour and next-month rules. These are sensitivity diagnostics, not independent
tests.

The computational gate passes, but the evidence does not justify strategy
construction. Any adjusted relation model must be specified in a new protocol
that treats these raw outcomes as observed exploratory evidence. Strict
point-in-time claims remain blocked by unresolved historical PDF identity.

## 2026-08-08: Freeze adjusted relations after descriptive inspection

The unadjusted relationship surface is already observed at commit `e321acd`.
The next protocol is therefore explicitly post-descriptive and exploratory. It
cannot produce untouched confirmatory evidence.

The primary model pools equal-weight asset-group outcomes, includes one of 11
primary narrative features, the matching text-length control, lagged MOM60,
lagged 20-session volatility, and asset-group fixed effects, and clusters
uncertainty by report event. Secondary asset-group coefficients receive no
p-values; dispersion models use frozen Newey-West lags. Benjamini-Hochberg
adjustment covers all 99 pooled tests and all 99 dispersion tests separately.

All three timing rules and all three horizons remain mandatory. Numerical gate
failures are reported as exclusions. No adjusted result permits portfolio
construction, and independent validation remains required.

## 2026-08-08: Amend the small-sample reference distribution

Protocol v1 specified CR1 cluster covariance and Newey-West covariance but did
not specify whether test statistics used a normal or Student t reference
distribution. The first implementation rehearsal exposed that omission and its
normal-approximation output is rejected before formal reporting.

Protocol v2 keeps the model grid, controls, covariance estimators, multiplicity
families, and 10% reference FDR unchanged. It adds the more conservative Student
t convention: event-cluster count minus one degrees of freedom for pooled
models and residual degrees of freedom for dispersion models. The amendment is
logged because this choice can affect a boundary result in a 31-event sample.
