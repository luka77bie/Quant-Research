from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from narrative_regime.baseline.attention import (
    FEATURE_WEIGHTS,
    LONG_WINDOW,
    PROXY_WEIGHT,
    SHORT_WINDOW,
    run_attention_reproduction,
)
from narrative_regime.baseline.momentum import run_momentum_baseline
from narrative_regime.data.audit import audit_provider_cache
from narrative_regime.data.comparison import compare_provider_caches
from narrative_regime.data.downloader import DownloadManager
from narrative_regime.data.models import FetchRequest
from narrative_regime.data.panel import (
    build_common_sample,
    validate_availability_metadata,
    validate_calendar_exceptions,
)
from narrative_regime.data.providers import build_providers
from narrative_regime.macro.archive import (
    MacroEvidenceArchive,
    audit_macro_evidence,
)
from narrative_regime.macro.catalog_validation import (
    MINIMUM_FAMILY_COVERAGE,
    MacroMonthlyArchive,
    audit_monthly_catalog,
    build_article_evidence_ledger,
    monthly_cache_path,
    summarize_fetch,
)
from narrative_regime.macro.discovery import (
    DEFAULT_INDEX_URLS,
    MacroCatalogDiscovery,
    archive_index_pages,
    build_coverage_catalog,
)
from narrative_regime.macro.panel import build_macro_panel
from narrative_regime.macro.payoff_atlas import (
    audit_payoff_atlas_protocol,
    load_payoff_atlas_protocol,
)
from narrative_regime.macro.pilot import audit_macro_release_pilot
from narrative_regime.macro.search_backfill import (
    NbsSearchBackfill,
    apply_reviewed_seeds,
)
from narrative_regime.macro.templates import audit_template_drift
from narrative_regime.narrative.adjusted_relations import (
    build_adjusted_market_relations,
    load_adjusted_relation_protocol,
)
from narrative_regime.narrative.archive import (
    NarrativeArchive,
    audit_archive,
    coverage_summary,
)
from narrative_regime.narrative.diagnostics import audit_policy_features
from narrative_regime.narrative.extraction import (
    extract_catalog_text,
    extraction_summary,
)
from narrative_regime.narrative.features import build_policy_features
from narrative_regime.narrative.market_relations import (
    build_descriptive_market_relations,
    load_market_relation_protocol,
)
from narrative_regime.narrative.sections import (
    parse_policy_sections,
    section_summary,
)
from narrative_regime.narrative.timing import build_timing_joins
from narrative_regime.provenance import build_run_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nrea")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="download daily ETF data")
    download.add_argument("--universe", type=Path, required=True)
    download.add_argument("--start", type=date.fromisoformat, required=True)
    download.add_argument("--end", type=date.fromisoformat, required=True)
    download.add_argument("--providers", default="tencent,akshare")
    download.add_argument(
        "--symbols",
        help="comma-separated universe symbols to resume selectively",
    )
    download.add_argument("--attempts", type=int, default=3)
    download.add_argument("--delay", type=float, default=1.0)
    download.add_argument("--max-consecutive-failures", type=int, default=3)
    download.add_argument("--refresh", action="store_true")
    download.add_argument("--root", type=Path, default=Path.cwd())

    audit = subparsers.add_parser("audit", help="audit a local provider cache")
    audit.add_argument("--universe", type=Path, required=True)
    audit.add_argument("--provider", required=True)
    audit.add_argument("--root", type=Path, default=Path.cwd())
    audit.add_argument("--output", type=Path)

    compare = subparsers.add_parser(
        "compare-providers", help="compare two isolated provider caches"
    )
    compare.add_argument("--left-provider", required=True)
    compare.add_argument("--right-provider", required=True)
    compare.add_argument("--symbols", required=True)
    compare.add_argument("--root", type=Path, default=Path.cwd())
    compare.add_argument("--output", type=Path, required=True)

    sample = subparsers.add_parser(
        "build-sample", help="build an audited single-provider common sample"
    )
    sample.add_argument("--universe", type=Path, required=True)
    sample.add_argument("--availability-sources", type=Path, required=True)
    sample.add_argument("--calendar-exceptions", type=Path, required=True)
    sample.add_argument("--provider", required=True)
    sample.add_argument("--start", type=date.fromisoformat, required=True)
    sample.add_argument("--end", type=date.fromisoformat, required=True)
    sample.add_argument("--reference-symbol", default="510300")
    sample.add_argument("--root", type=Path, default=Path.cwd())
    sample.add_argument("--output-dir", type=Path, required=True)

    baseline = subparsers.add_parser("baseline", help="run frozen MOM60 baseline")
    baseline.add_argument("--prices", type=Path, required=True)
    baseline.add_argument("--output-dir", type=Path, required=True)
    baseline.add_argument("--lookback", type=int, default=60)
    baseline.add_argument("--top-n", type=int, default=3)
    baseline.add_argument("--cost-bps", type=float, default=10.0)

    attention = subparsers.add_parser(
        "attention-reproduction",
        help="reproduce the fixed predecessor market-attention control",
    )
    attention.add_argument("--prices", type=Path, required=True)
    attention.add_argument("--output-dir", type=Path, required=True)
    attention.add_argument("--top-n", type=int, default=3)
    attention.add_argument("--cost-bps", type=float, default=10.0)

    narrative_fetch = subparsers.add_parser(
        "narrative-fetch", help="download a reviewed narrative document catalog"
    )
    narrative_fetch.add_argument("--catalog", type=Path, required=True)
    narrative_fetch.add_argument("--sources", type=Path, required=True)
    narrative_fetch.add_argument("--root", type=Path, default=Path.cwd())
    narrative_fetch.add_argument("--attempts", type=int, default=3)
    narrative_fetch.add_argument("--refresh", action="store_true")

    narrative_audit = subparsers.add_parser(
        "narrative-audit", help="audit cached narrative documents and coverage"
    )
    narrative_audit.add_argument("--catalog", type=Path, required=True)
    narrative_audit.add_argument("--sources", type=Path, required=True)
    narrative_audit.add_argument("--root", type=Path, default=Path.cwd())
    narrative_audit.add_argument("--output-dir", type=Path, required=True)
    narrative_audit.add_argument("--coverage-start", default="2018-03-31")
    narrative_audit.add_argument("--coverage-end", default="2025-12-31")

    narrative_extract = subparsers.add_parser(
        "narrative-extract", help="extract and quality-audit archived PDF text"
    )
    narrative_extract.add_argument("--catalog", type=Path, required=True)
    narrative_extract.add_argument("--sources", type=Path, required=True)
    narrative_extract.add_argument("--root", type=Path, default=Path.cwd())
    narrative_extract.add_argument("--output-dir", type=Path, required=True)
    narrative_extract.add_argument("--minimum-characters", type=int, default=10_000)
    narrative_extract.add_argument(
        "--maximum-empty-page-ratio", type=float, default=0.10
    )
    narrative_extract.add_argument(
        "--maximum-replacement-ratio", type=float, default=0.001
    )
    narrative_extract.add_argument("--minimum-cjk-ratio", type=float, default=0.50)

    narrative_sections = subparsers.add_parser(
        "narrative-sections",
        help="parse and quality-audit forward-looking policy sections",
    )
    narrative_sections.add_argument("--catalog", type=Path, required=True)
    narrative_sections.add_argument("--sources", type=Path, required=True)
    narrative_sections.add_argument("--root", type=Path, default=Path.cwd())
    narrative_sections.add_argument("--output-dir", type=Path, required=True)
    narrative_sections.add_argument("--minimum-characters", type=int, default=1_500)
    narrative_sections.add_argument("--maximum-characters", type=int, default=6_000)
    narrative_sections.add_argument("--minimum-cjk-ratio", type=float, default=0.60)

    narrative_features = subparsers.add_parser(
        "narrative-features",
        help="build frozen return-blind policy-language diagnostics",
    )
    narrative_features.add_argument("--catalog", type=Path, required=True)
    narrative_features.add_argument("--sources", type=Path, required=True)
    narrative_features.add_argument("--lexicon", type=Path, required=True)
    narrative_features.add_argument("--root", type=Path, default=Path.cwd())
    narrative_features.add_argument("--output-dir", type=Path, required=True)

    narrative_timing = subparsers.add_parser(
        "narrative-timing",
        help="map frozen narrative features to delayed market sessions",
    )
    narrative_timing.add_argument("--features", type=Path, required=True)
    narrative_timing.add_argument("--prices", type=Path, required=True)
    narrative_timing.add_argument("--reference-symbol", default="510300")
    narrative_timing.add_argument("--output-dir", type=Path, required=True)

    narrative_diagnostics = subparsers.add_parser(
        "narrative-diagnostics",
        help="audit frozen policy-feature stability without market data",
    )
    narrative_diagnostics.add_argument("--features", type=Path, required=True)
    narrative_diagnostics.add_argument("--output-dir", type=Path, required=True)

    market_relations = subparsers.add_parser(
        "market-relations",
        help="run frozen descriptive narrative-market relationship protocol",
    )
    market_relations.add_argument("--features", type=Path, required=True)
    market_relations.add_argument("--schedule", type=Path, required=True)
    market_relations.add_argument("--prices", type=Path, required=True)
    market_relations.add_argument("--universe", type=Path, required=True)
    market_relations.add_argument("--protocol", type=Path, required=True)
    market_relations.add_argument("--reference-symbol", default="510300")
    market_relations.add_argument("--output-dir", type=Path, required=True)

    adjusted_relations = subparsers.add_parser(
        "adjusted-relations",
        help="run frozen post-descriptive adjusted relationship protocol",
    )
    adjusted_relations.add_argument("--panel", type=Path, required=True)
    adjusted_relations.add_argument("--protocol", type=Path, required=True)
    adjusted_relations.add_argument("--output-dir", type=Path, required=True)

    macro_pilot = subparsers.add_parser(
        "macro-release-pilot",
        help="audit the return-blind official macro release feasibility catalog",
    )
    macro_pilot.add_argument("--catalog", type=Path, required=True)
    macro_pilot.add_argument("--output-dir", type=Path, required=True)

    macro_fetch = subparsers.add_parser(
        "macro-evidence-fetch",
        help="cache reviewed official macro release pages with checksums",
    )
    macro_fetch.add_argument("--catalog", type=Path, required=True)
    macro_fetch.add_argument("--evidence", type=Path, required=True)
    macro_fetch.add_argument("--root", type=Path, default=Path.cwd())
    macro_fetch.add_argument("--attempts", type=int, default=3)
    macro_fetch.add_argument("--refresh", action="store_true")

    macro_audit = subparsers.add_parser(
        "macro-evidence-audit",
        help="verify locked macro page checksums and registered evidence text",
    )
    macro_audit.add_argument("--catalog", type=Path, required=True)
    macro_audit.add_argument("--evidence", type=Path, required=True)
    macro_audit.add_argument("--root", type=Path, default=Path.cwd())
    macro_audit.add_argument("--output-dir", type=Path, required=True)

    template_audit = subparsers.add_parser(
        "macro-template-audit",
        help="audit deterministic macro extraction across source-year anchors",
    )
    template_audit.add_argument("--catalog", type=Path, required=True)
    template_audit.add_argument("--root", type=Path, default=Path.cwd())
    template_audit.add_argument("--output-dir", type=Path, required=True)

    macro_discovery = subparsers.add_parser(
        "macro-catalog-discovery",
        help="enumerate official index pages and audit monthly source coverage",
    )
    macro_discovery.add_argument("--start", default="2018-01")
    macro_discovery.add_argument("--end", default="2025-12")
    macro_discovery.add_argument("--attempts", type=int, default=3)
    macro_discovery.add_argument("--output-dir", type=Path, required=True)

    macro_backfill = subparsers.add_parser(
        "macro-catalog-backfill",
        help="backfill missing NBS months through exact-title official search",
    )
    macro_backfill.add_argument("--catalog", type=Path, required=True)
    macro_backfill.add_argument("--attempts", type=int, default=3)
    macro_backfill.add_argument("--max-pages", type=int, default=5)
    macro_backfill.add_argument("--output-dir", type=Path, required=True)

    macro_seeds = subparsers.add_parser(
        "macro-catalog-apply-seeds",
        help="apply reviewed official candidates pending article validation",
    )
    macro_seeds.add_argument("--catalog", type=Path, required=True)
    macro_seeds.add_argument("--seeds", type=Path, required=True)
    macro_seeds.add_argument("--output-dir", type=Path, required=True)

    macro_catalog_fetch = subparsers.add_parser(
        "macro-catalog-fetch",
        help="cache full monthly macro catalog pages with per-record resume",
    )
    macro_catalog_fetch.add_argument("--catalog", type=Path, required=True)
    macro_catalog_fetch.add_argument("--root", type=Path, default=Path.cwd())
    macro_catalog_fetch.add_argument("--attempts", type=int, default=3)
    macro_catalog_fetch.add_argument("--delay", type=float, default=0.2)
    macro_catalog_fetch.add_argument(
        "--record-ids", help="comma-separated record IDs to resume selectively"
    )
    macro_catalog_fetch.add_argument("--refresh", action="store_true")
    macro_catalog_fetch.add_argument("--output-dir", type=Path, required=True)

    macro_catalog_validate = subparsers.add_parser(
        "macro-catalog-validate",
        help="validate cached macro articles without reading market returns",
    )
    macro_catalog_validate.add_argument("--catalog", type=Path, required=True)
    macro_catalog_validate.add_argument("--root", type=Path, default=Path.cwd())
    macro_catalog_validate.add_argument("--output-dir", type=Path, required=True)

    macro_panel = subparsers.add_parser(
        "macro-panel",
        help="build a frozen return-blind macro state chronology",
    )
    macro_panel.add_argument("--ledger", type=Path, required=True)
    macro_panel.add_argument("--protocol", type=Path, required=True)
    macro_panel.add_argument("--output-dir", type=Path, required=True)

    payoff_protocol = subparsers.add_parser(
        "macro-payoff-protocol-audit",
        help="audit the frozen payoff-atlas plan before reading ETF outcomes",
    )
    payoff_protocol.add_argument("--protocol", type=Path, required=True)
    payoff_protocol.add_argument("--universe", type=Path, required=True)
    payoff_protocol.add_argument("--output-dir", type=Path, required=True)
    return parser


def run_download(args: argparse.Namespace) -> int:
    universe = _read_universe(args.universe)
    universe = _select_universe_symbols(universe, args.symbols)

    provider_names = [item.strip() for item in args.providers.split(",") if item]
    manager = DownloadManager(
        root=args.root,
        providers=build_providers(provider_names),
        attempts=args.attempts,
        inter_symbol_delay_seconds=args.delay,
        max_consecutive_failures=args.max_consecutive_failures,
    )
    requests = []
    for row in universe.to_dict(orient="records"):
        request_start = args.start
        available_from = row.get("available_from")
        if pd.notna(available_from):
            request_start = max(request_start, date.fromisoformat(str(available_from)))
        requests.append(
            FetchRequest(symbol=str(row["symbol"]), start=request_start, end=args.end)
        )
    results = manager.download_many(requests, refresh=args.refresh)

    print(f"{'symbol':<10} {'provider':<10} {'status':<12} {'rows':>8}")
    print("-" * 44)
    for result in results:
        print(
            f"{result.symbol:<10} {result.provider:<10} "
            f"{result.status:<12} {result.rows:>8}"
        )
        if result.error:
            print(f"  error: {result.error}")
        for issue in result.coverage_issues:
            print(f"  coverage: {issue}")

    summary_path = args.root / "data" / "manifests" / "latest_download_summary.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "symbol": result.symbol,
                "provider": result.provider,
                "status": result.status,
                "rows": result.rows,
                "cache_path": str(result.cache_path) if result.cache_path else "",
                "coverage_issues": "; ".join(result.coverage_issues),
                "error": result.error or "",
            }
            for result in results
        ]
    ).to_csv(summary_path, index=False)

    incomplete = [
        result for result in results if result.status not in {"downloaded", "cached"}
    ]
    print(f"\ncomplete={len(results) - len(incomplete)} incomplete={len(incomplete)}")
    print(f"summary={summary_path}")
    return 1 if incomplete else 0


def _read_universe(path: Path) -> pd.DataFrame:
    universe = pd.read_csv(path, dtype={"symbol": str})
    if "symbol" not in universe:
        raise ValueError("universe file must contain a symbol column")
    if universe["symbol"].duplicated().any():
        duplicates = sorted(universe.loc[universe["symbol"].duplicated(), "symbol"])
        duplicate_text = ", ".join(duplicates)
        raise ValueError(f"universe contains duplicate symbols: {duplicate_text}")
    return universe


def _select_universe_symbols(
    universe: pd.DataFrame,
    symbols_argument: str | None,
) -> pd.DataFrame:
    if symbols_argument is None:
        return universe

    requested = [item.strip() for item in symbols_argument.split(",") if item.strip()]
    if not requested:
        raise ValueError("--symbols must contain at least one symbol")
    if len(requested) != len(set(requested)):
        raise ValueError("--symbols contains duplicate symbols")

    universe_symbols = set(universe["symbol"].astype(str))
    unknown = sorted(set(requested) - universe_symbols)
    if unknown:
        raise ValueError(f"--symbols not found in universe: {', '.join(unknown)}")

    requested_set = set(requested)
    return universe.loc[
        universe["symbol"].astype(str).isin(requested_set)
    ].reset_index(drop=True)


def run_audit(args: argparse.Namespace) -> int:
    universe = _read_universe(args.universe)
    report = audit_provider_cache(
        args.root,
        args.provider,
        universe["symbol"].astype(str).tolist(),
    )
    output = args.output or (
        args.root / "data" / "manifests" / f"{args.provider}_cache_audit.csv"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(output, index=False)
    counts = report["audit_status"].value_counts().to_dict()
    print(" ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    print(f"report={output}")
    return 0 if report["audit_status"].eq("ready").all() else 1


def run_compare_providers(args: argparse.Namespace) -> int:
    symbols = [item.strip() for item in args.symbols.split(",") if item.strip()]
    if not symbols:
        raise ValueError("--symbols must contain at least one symbol")
    if len(symbols) != len(set(symbols)):
        raise ValueError("--symbols contains duplicate symbols")
    report = compare_provider_caches(
        args.root,
        args.left_provider,
        args.right_provider,
        symbols,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.output, index=False)
    counts = report["status"].value_counts().to_dict()
    print(" ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    print(f"report={args.output}")
    return 0 if report["status"].eq("ready").all() else 1


def run_build_sample(args: argparse.Namespace) -> int:
    universe = _read_universe(args.universe)
    sources = pd.read_csv(args.availability_sources, dtype={"symbol": str})
    exceptions = pd.read_csv(args.calendar_exceptions, dtype={"symbol": str})
    validate_availability_metadata(universe, sources)
    validate_calendar_exceptions(universe, exceptions)
    result = build_common_sample(
        root=args.root,
        provider=args.provider,
        universe=universe,
        start=args.start,
        end=args.end,
        reference_symbol=args.reference_symbol,
        calendar_exceptions=exceptions,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    panel_audit_path = args.output_dir / "common_sample_audit.csv"
    cache_audit_path = args.output_dir / "common_sample_cache_audit.csv"
    sample_path = args.output_dir / "common_sample.csv"
    result.panel_audit.to_csv(panel_audit_path, index=False)
    result.cache_audit.to_csv(cache_audit_path, index=False)
    outputs = [panel_audit_path, cache_audit_path]
    if result.ready:
        result.sample.to_csv(sample_path, index=False, date_format="%Y-%m-%d")
        outputs.append(sample_path)

    cache_inputs = []
    for symbol in universe["symbol"].astype(str):
        cache_path = args.root / "data" / "raw" / args.provider / f"{symbol}.csv"
        metadata_path = cache_path.with_suffix(".meta.json")
        cache_inputs.extend(
            path for path in (cache_path, metadata_path) if path.exists()
        )
    command = [
        "nrea",
        "build-sample",
        "--universe",
        str(args.universe),
        "--availability-sources",
        str(args.availability_sources),
        "--provider",
        args.provider,
        "--calendar-exceptions",
        str(args.calendar_exceptions),
        "--start",
        args.start.isoformat(),
        "--end",
        args.end.isoformat(),
        "--reference-symbol",
        args.reference_symbol,
        "--root",
        str(args.root),
        "--output-dir",
        str(args.output_dir),
    ]
    manifest = build_run_manifest(
        input_path=args.universe,
        additional_inputs=[
            args.availability_sources,
            args.calendar_exceptions,
            *cache_inputs,
        ],
        command=command,
        parameters={
            "provider": args.provider,
            "start": args.start.isoformat(),
            "end": args.end.isoformat(),
            "reference_symbol": args.reference_symbol,
            "outcome": "ready" if result.ready else "blocked",
        },
        outputs=outputs,
        repository=Path.cwd(),
    )
    (args.output_dir / "common_sample_run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    counts = result.panel_audit["status"].value_counts().to_dict()
    print(" ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    print(f"output_dir={args.output_dir}")
    return 0 if result.ready else 1


def run_baseline(args: argparse.Namespace) -> int:
    result = run_momentum_baseline(
        pd.read_csv(args.prices, dtype={"symbol": str}),
        lookback=args.lookback,
        top_n=args.top_n,
        cost_bps=args.cost_bps,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    daily_path = args.output_dir / "mom60_daily.csv"
    selections_path = args.output_dir / "mom60_selections.csv"
    metrics_path = args.output_dir / "mom60_metrics.json"
    result.daily.to_csv(daily_path, date_format="%Y-%m-%d")
    result.selections.to_csv(selections_path, index=False, date_format="%Y-%m-%d")
    metrics_path.write_text(
        json.dumps(result.metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = build_run_manifest(
        input_path=args.prices,
        command=[
            "nrea",
            "baseline",
            "--prices",
            str(args.prices),
            "--output-dir",
            str(args.output_dir),
            "--lookback",
            str(args.lookback),
            "--top-n",
            str(args.top_n),
            "--cost-bps",
            str(args.cost_bps),
        ],
        parameters={
            "lookback": args.lookback,
            "top_n": args.top_n,
            "cost_bps": args.cost_bps,
            "signal_frequency": "calendar_month_end",
            "execution_delay_panel_rows": 1,
        },
        outputs=[daily_path, selections_path, metrics_path],
        repository=Path.cwd(),
    )
    (args.output_dir / "mom60_run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result.metrics, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return 0


def run_attention(args: argparse.Namespace) -> int:
    prices = pd.read_csv(args.prices, dtype={"symbol": str})
    result = run_attention_reproduction(
        prices,
        top_n=args.top_n,
        cost_bps=args.cost_bps,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_frames = {
        "mom60_daily.csv": (result.momentum.daily, True),
        "mom60_selections.csv": (result.momentum.selections, False),
        "attention_composite_daily.csv": (result.composite.daily, True),
        "attention_composite_selections.csv": (result.composite.selections, False),
        "attention_signals.csv": (result.signals, False),
        "attention_subperiod_comparison.csv": (result.comparison, False),
    }
    output_paths = []
    for filename, (frame, include_index) in output_frames.items():
        path = args.output_dir / filename
        frame.to_csv(
            path,
            index=include_index,
            date_format="%Y-%m-%d",
        )
        output_paths.append(path)

    metrics_path = args.output_dir / "attention_reproduction_metrics.json"
    metrics = {
        "activity_value_source_counts": result.activity_source_counts,
        "fixed_parameters": {
            "short_window": SHORT_WINDOW,
            "long_window": LONG_WINDOW,
            "proxy_weight": PROXY_WEIGHT,
            "feature_weights": FEATURE_WEIGHTS,
            "top_n": args.top_n,
            "cost_bps": args.cost_bps,
        },
        "mom60": result.momentum.metrics,
        "attention_composite": result.composite.metrics,
    }
    metrics_path.write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output_paths.append(metrics_path)
    manifest = build_run_manifest(
        input_path=args.prices,
        command=[
            "nrea",
            "attention-reproduction",
            "--prices",
            str(args.prices),
            "--output-dir",
            str(args.output_dir),
            "--top-n",
            str(args.top_n),
            "--cost-bps",
            str(args.cost_bps),
        ],
        parameters={
            **metrics["fixed_parameters"],
            "signal_frequency": "calendar_month_end",
            "execution_delay_panel_rows": 1,
            "amount_fallback": "close_x_volume",
        },
        outputs=output_paths,
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "attention_reproduction_run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metrics, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return 0


def run_narrative_fetch(args: argparse.Namespace) -> int:
    catalog = pd.read_csv(args.catalog, dtype=str, keep_default_na=False)
    sources = pd.read_csv(args.sources, dtype=str, keep_default_na=False)
    archive = NarrativeArchive(args.root, attempts=args.attempts)
    results = archive.fetch_catalog(catalog, sources, refresh=args.refresh)
    summary_path = args.root / "data" / "manifests" / "narrative_fetch_summary.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(summary_path, index=False)
    print(results.to_string(index=False))
    print(f"summary={summary_path}")
    return 0 if results["status"].isin({"downloaded", "cached"}).all() else 1


def run_narrative_audit(args: argparse.Namespace) -> int:
    catalog = pd.read_csv(args.catalog, dtype=str, keep_default_na=False)
    sources = pd.read_csv(args.sources, dtype=str, keep_default_na=False)
    audit = audit_archive(args.root, catalog, sources)
    summary = coverage_summary(
        audit,
        start=args.coverage_start,
        end=args.coverage_end,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = args.output_dir / "narrative_archive_audit.csv"
    summary_path = args.output_dir / "narrative_coverage_summary.json"
    audit.to_csv(audit_path, index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    raw_inputs = []
    for row in audit.to_dict("records"):
        base = (
            args.root
            / "data"
            / "raw"
            / "narrative"
            / str(row["source_id"])
            / f"{row['record_id']}"
        )
        raw_inputs.extend(
            path for path in (base.with_suffix(".pdf"), base.with_suffix(".meta.json"))
            if path.exists()
        )
        snapshot_path = (
            args.root
            / "data"
            / "raw"
            / "narrative_snapshots"
            / str(row["source_id"])
            / f"{row['record_id']}.pdf"
        )
        if snapshot_path.exists():
            raw_inputs.append(snapshot_path)
    manifest = build_run_manifest(
        input_path=args.catalog,
        additional_inputs=[args.sources, *raw_inputs],
        command=[
            "nrea",
            "narrative-audit",
            "--catalog",
            str(args.catalog),
            "--sources",
            str(args.sources),
            "--root",
            str(args.root),
            "--output-dir",
            str(args.output_dir),
            "--coverage-start",
            args.coverage_start,
            "--coverage-end",
            args.coverage_end,
        ],
        parameters={
            "coverage_start": args.coverage_start,
            "coverage_end": args.coverage_end,
            "required_point_in_time_status": "verified",
        },
        outputs=[audit_path, summary_path],
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "narrative_archive_run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(audit.to_string(index=False))
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return 0 if summary["modeling_gate"] == "pass" else 1


def run_narrative_extract(args: argparse.Namespace) -> int:
    catalog = pd.read_csv(args.catalog, dtype=str, keep_default_na=False)
    sources = pd.read_csv(args.sources, dtype=str, keep_default_na=False)
    results = extract_catalog_text(
        args.root,
        catalog,
        sources,
        minimum_characters=args.minimum_characters,
        maximum_empty_page_ratio=args.maximum_empty_page_ratio,
        maximum_replacement_ratio=args.maximum_replacement_ratio,
        minimum_cjk_ratio=args.minimum_cjk_ratio,
    )
    summary = extraction_summary(results)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = args.output_dir / "narrative_text_audit.csv"
    summary_path = args.output_dir / "narrative_text_summary.json"
    results.to_csv(audit_path, index=False)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    raw_inputs = []
    text_outputs = []
    for row in results.to_dict("records"):
        raw_base = (
            args.root
            / "data/raw/narrative"
            / str(row["source_id"])
            / str(row["record_id"])
        )
        raw_inputs.extend(
            path
            for path in (
                raw_base.with_suffix(".pdf"),
                raw_base.with_suffix(".meta.json"),
            )
            if path.exists()
        )
        text_path = Path(str(row["text_path"]))
        text_outputs.extend([text_path, text_path.with_suffix(".meta.json")])
    manifest = build_run_manifest(
        input_path=args.catalog,
        additional_inputs=[args.sources, *raw_inputs],
        command=[
            "nrea",
            "narrative-extract",
            "--catalog",
            str(args.catalog),
            "--sources",
            str(args.sources),
            "--root",
            str(args.root),
            "--output-dir",
            str(args.output_dir),
            "--minimum-characters",
            str(args.minimum_characters),
            "--maximum-empty-page-ratio",
            str(args.maximum_empty_page_ratio),
            "--maximum-replacement-ratio",
            str(args.maximum_replacement_ratio),
            "--minimum-cjk-ratio",
            str(args.minimum_cjk_ratio),
        ],
        parameters={
            "minimum_characters": args.minimum_characters,
            "maximum_empty_page_ratio": args.maximum_empty_page_ratio,
            "maximum_replacement_ratio": args.maximum_replacement_ratio,
            "minimum_cjk_ratio": args.minimum_cjk_ratio,
            "research_use": "exploratory_only",
        },
        outputs=[*text_outputs, audit_path, summary_path],
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "narrative_text_run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(results.to_string(index=False))
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return 0 if summary["extraction_gate"] == "pass" else 1


def run_narrative_sections(args: argparse.Namespace) -> int:
    catalog = pd.read_csv(args.catalog, dtype=str, keep_default_na=False)
    sources = pd.read_csv(args.sources, dtype=str, keep_default_na=False)
    results = parse_policy_sections(
        args.root,
        catalog,
        sources,
        minimum_characters=args.minimum_characters,
        maximum_characters=args.maximum_characters,
        minimum_cjk_ratio=args.minimum_cjk_ratio,
    )
    summary = section_summary(results)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = args.output_dir / "narrative_section_audit.csv"
    summary_path = args.output_dir / "narrative_section_summary.json"
    results.to_csv(audit_path, index=False)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    text_inputs = []
    section_outputs = []
    for row in results.to_dict("records"):
        text_path = args.root / str(row["section_path"])
        source_path = (
            args.root
            / "data"
            / "processed"
            / "narrative_text"
            / f"{row['record_id']}.txt"
        )
        text_inputs.extend([source_path, source_path.with_suffix(".meta.json")])
        section_outputs.extend([text_path, text_path.with_suffix(".meta.json")])
    manifest = build_run_manifest(
        input_path=args.catalog,
        additional_inputs=[args.sources, *text_inputs],
        command=[
            "nrea",
            "narrative-sections",
            "--catalog",
            str(args.catalog),
            "--sources",
            str(args.sources),
            "--root",
            str(args.root),
            "--output-dir",
            str(args.output_dir),
            "--minimum-characters",
            str(args.minimum_characters),
            "--maximum-characters",
            str(args.maximum_characters),
            "--minimum-cjk-ratio",
            str(args.minimum_cjk_ratio),
        ],
        parameters={
            "minimum_characters": args.minimum_characters,
            "maximum_characters": args.maximum_characters,
            "minimum_cjk_ratio": args.minimum_cjk_ratio,
            "minimum_required_ready_records": 30,
            "research_use": "exploratory_only",
        },
        outputs=[*section_outputs, audit_path, summary_path],
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "narrative_section_run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(results.to_string(index=False))
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return 0 if summary["section_gate"] == "pass" else 1


def run_narrative_features(args: argparse.Namespace) -> int:
    catalog = pd.read_csv(args.catalog, dtype=str, keep_default_na=False)
    sources = pd.read_csv(args.sources, dtype=str, keep_default_na=False)
    lexicon = pd.read_csv(args.lexicon, dtype=str, keep_default_na=False)
    result = build_policy_features(args.root, catalog, sources, lexicon)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    feature_path = args.output_dir / "policy_features.csv"
    counts_path = args.output_dir / "policy_term_counts.csv"
    summary_path = args.output_dir / "policy_feature_summary.json"
    result.features.to_csv(feature_path, index=False)
    result.term_counts.to_csv(counts_path, index=False)
    summary_path.write_text(
        json.dumps(result.summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    section_inputs = []
    for record_id in result.features["record_id"].astype(str):
        section_path = (
            args.root / "data" / "processed" / "narrative_sections" / f"{record_id}.txt"
        )
        section_inputs.extend([section_path, section_path.with_suffix(".meta.json")])
    manifest = build_run_manifest(
        input_path=args.catalog,
        additional_inputs=[args.sources, args.lexicon, *section_inputs],
        command=[
            "nrea",
            "narrative-features",
            "--catalog",
            str(args.catalog),
            "--sources",
            str(args.sources),
            "--lexicon",
            str(args.lexicon),
            "--root",
            str(args.root),
            "--output-dir",
            str(args.output_dir),
        ],
        parameters={
            "similarity": "character_bigram_cosine",
            "term_normalization": "remove_whitespace_exact_match",
            "return_data_used": False,
            "composite_score_created": False,
            "research_use": "exploratory_only",
        },
        outputs=[feature_path, counts_path, summary_path],
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "policy_feature_run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(result.features.to_string(index=False))
    print(json.dumps(result.summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return 0 if result.summary["feature_gate"] == "pass" else 1


def run_narrative_timing(args: argparse.Namespace) -> int:
    features = pd.read_csv(args.features, dtype={"record_id": str})
    market_calendar = pd.read_csv(
        args.prices,
        usecols=["date", "symbol"],
        dtype={"symbol": str},
    )
    result = build_timing_joins(
        features,
        market_calendar,
        reference_symbol=args.reference_symbol,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    schedule_path = args.output_dir / "narrative_activation_schedule.csv"
    calendar_path = args.output_dir / "narrative_feature_calendar.csv"
    summary_path = args.output_dir / "narrative_timing_summary.json"
    result.schedule.to_csv(schedule_path, index=False)
    result.calendar.to_csv(calendar_path, index=False)
    summary_path.write_text(
        json.dumps(result.summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = build_run_manifest(
        input_path=args.features,
        additional_inputs=[args.prices],
        command=[
            "nrea",
            "narrative-timing",
            "--features",
            str(args.features),
            "--prices",
            str(args.prices),
            "--reference-symbol",
            args.reference_symbol,
            "--output-dir",
            str(args.output_dir),
        ],
        parameters={
            "protocols": ["delay_24h", "delay_48h", "next_month"],
            "market_timezone": "Asia/Shanghai",
            "session_open": "09:30",
            "reference_symbol": args.reference_symbol,
            "price_values_used": False,
            "return_data_used": False,
            "research_use": "exploratory_only",
        },
        outputs=[schedule_path, calendar_path, summary_path],
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "narrative_timing_run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(result.schedule.to_string(index=False))
    print(json.dumps(result.summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return 0 if result.summary["timing_gate"] == "pass" else 1


def run_narrative_diagnostics(args: argparse.Namespace) -> int:
    features = pd.read_csv(args.features)
    result = audit_policy_features(features)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_frames = {
        "feature_distribution.csv": result.distribution,
        "feature_missingness.csv": result.missingness,
        "feature_persistence.csv": result.persistence,
        "feature_pearson_correlation.csv": result.pearson,
        "feature_spearman_correlation.csv": result.spearman,
        "feature_high_correlation_pairs.csv": result.high_correlation_pairs,
    }
    output_paths = []
    for filename, frame in output_frames.items():
        path = args.output_dir / filename
        frame.to_csv(path, index=filename.endswith("correlation.csv"))
        output_paths.append(path)
    summary_path = args.output_dir / "feature_diagnostic_summary.json"
    summary_path.write_text(
        json.dumps(result.summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output_paths.append(summary_path)
    manifest = build_run_manifest(
        input_path=args.features,
        command=[
            "nrea",
            "narrative-diagnostics",
            "--features",
            str(args.features),
            "--output-dir",
            str(args.output_dir),
        ],
        parameters={
            "correlations": ["pearson", "spearman"],
            "high_absolute_correlation_threshold": 0.90,
            "market_data_used": False,
            "return_data_used": False,
            "feature_selection_performed": False,
            "research_use": "exploratory_only",
        },
        outputs=output_paths,
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "feature_diagnostic_run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(result.distribution.to_string(index=False))
    print(json.dumps(result.summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return 0 if result.summary["diagnostic_gate"] == "pass" else 1


def run_market_relations(args: argparse.Namespace) -> int:
    features = pd.read_csv(args.features, dtype={"record_id": str})
    schedule = pd.read_csv(args.schedule, dtype={"record_id": str})
    prices = pd.read_csv(args.prices, dtype={"symbol": str})
    universe = pd.read_csv(args.universe, dtype={"symbol": str})
    protocol = load_market_relation_protocol(args.protocol)
    result = build_descriptive_market_relations(
        features,
        schedule,
        prices,
        universe,
        protocol,
        reference_symbol=args.reference_symbol,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_frames = {
        "market_relation_audit.csv": result.audit,
        "market_relation_panel.csv": result.panel,
        "asset_group_outcomes.csv": result.asset_group_outcomes,
        "dispersion_outcomes.csv": result.dispersion_outcomes,
        "symbol_relations.csv": result.symbol_relations,
        "asset_group_relations.csv": result.asset_group_relations,
        "dispersion_relations.csv": result.dispersion_relations,
    }
    output_paths = []
    for filename, frame in output_frames.items():
        path = args.output_dir / filename
        frame.to_csv(path, index=False)
        output_paths.append(path)
    summary_path = args.output_dir / "market_relation_summary.json"
    summary_path.write_text(
        json.dumps(result.summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output_paths.append(summary_path)
    manifest = build_run_manifest(
        input_path=args.features,
        additional_inputs=[args.schedule, args.prices, args.universe, args.protocol],
        command=[
            "nrea",
            "market-relations",
            "--features",
            str(args.features),
            "--schedule",
            str(args.schedule),
            "--prices",
            str(args.prices),
            "--universe",
            str(args.universe),
            "--protocol",
            str(args.protocol),
            "--reference-symbol",
            args.reference_symbol,
            "--output-dir",
            str(args.output_dir),
        ],
        parameters={
            "protocol_status": protocol["status"],
            "timing_protocols": protocol["timing_protocols"],
            "forward_windows_reference_sessions": protocol[
                "forward_windows_reference_sessions"
            ],
            "return_convention": protocol["return_convention"],
            "control_convention": protocol["control_convention"],
            "portfolio_constructed": False,
            "specification_selected": False,
            "inferential_tests_performed": False,
            "research_use": "exploratory_only",
        },
        outputs=output_paths,
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "market_relation_run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result.summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return 0 if result.summary["market_relation_gate"] == "pass" else 1


def run_adjusted_relations(args: argparse.Namespace) -> int:
    panel = pd.read_csv(
        args.panel,
        dtype={"record_id": str, "symbol": str},
    )
    protocol = load_adjusted_relation_protocol(args.protocol)
    result = build_adjusted_market_relations(panel, protocol)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_frames = {
        "adjusted_asset_group_panel.csv": result.asset_group_panel,
        "adjusted_dispersion_panel.csv": result.dispersion_panel,
        "pooled_adjusted_relations.csv": result.pooled_relations,
        "asset_group_adjusted_relations.csv": result.asset_group_relations,
        "dispersion_adjusted_relations.csv": result.dispersion_relations,
    }
    output_paths = []
    for filename, frame in output_frames.items():
        path = args.output_dir / filename
        frame.to_csv(path, index=False)
        output_paths.append(path)
    summary_path = args.output_dir / "adjusted_relation_summary.json"
    summary_path.write_text(
        json.dumps(result.summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output_paths.append(summary_path)
    manifest = build_run_manifest(
        input_path=args.panel,
        additional_inputs=[args.protocol],
        command=[
            "nrea",
            "adjusted-relations",
            "--panel",
            str(args.panel),
            "--protocol",
            str(args.protocol),
            "--output-dir",
            str(args.output_dir),
        ],
        parameters={
            "protocol_status": protocol["status"],
            "evidence_status": protocol["evidence_status"],
            "descriptive_results_already_observed_at_commit": protocol[
                "descriptive_results_already_observed_at_commit"
            ],
            "timing_protocols": protocol["timing_protocols"],
            "forward_windows_reference_sessions": protocol[
                "forward_windows_reference_sessions"
            ],
            "models": protocol["models"],
            "multiplicity": protocol["multiplicity"],
            "portfolio_constructed": False,
            "confirmatory_claim_allowed": False,
        },
        outputs=output_paths,
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "adjusted_relation_run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result.summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return 0 if result.summary["adjusted_relation_gate"] == "pass" else 1


def run_macro_release_pilot(args: argparse.Namespace) -> int:
    catalog = pd.read_csv(args.catalog, dtype={"record_id": str})
    result = audit_macro_release_pilot(catalog)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = args.output_dir / "macro_release_pilot_audit.csv"
    result.audit.to_csv(audit_path, index=False)
    summary_path = args.output_dir / "macro_release_pilot_summary.json"
    summary_path.write_text(
        json.dumps(result.summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = build_run_manifest(
        input_path=args.catalog,
        parameters={
            "expected_dimensions": ["growth", "inflation", "liquidity"],
            "expected_records_per_dimension": 4,
            "minimum_original_release_pages": 10,
            "etf_returns_read": False,
            "regime_thresholds_constructed": False,
            "portfolio_constructed": False,
        },
        command=[
            "nrea",
            "macro-release-pilot",
            "--catalog",
            str(args.catalog),
            "--output-dir",
            str(args.output_dir),
        ],
        outputs=[audit_path, summary_path],
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "macro_release_pilot_run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result.summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return (
        0
        if result.summary["macro_release_pilot_gate"]
        == "pass_publication_record_only"
        else 1
    )


def run_macro_evidence_fetch(args: argparse.Namespace) -> int:
    catalog = pd.read_csv(args.catalog, dtype=str, keep_default_na=False)
    evidence = pd.read_csv(args.evidence, dtype=str, keep_default_na=False)
    archive = MacroEvidenceArchive(args.root, attempts=args.attempts)
    results = archive.fetch_catalog(catalog, evidence, refresh=args.refresh)
    summary_path = args.root / "data" / "manifests" / "macro_evidence_fetch.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(summary_path, index=False)
    print(results.to_string(index=False))
    print(f"summary={summary_path}")
    return 0 if results["status"].isin({"downloaded", "cached"}).all() else 1


def run_macro_evidence_audit(args: argparse.Namespace) -> int:
    catalog = pd.read_csv(args.catalog, dtype=str, keep_default_na=False)
    evidence = pd.read_csv(args.evidence, dtype=str, keep_default_na=False)
    audit, summary = audit_macro_evidence(args.root, catalog, evidence)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = args.output_dir / "macro_evidence_audit.csv"
    summary_path = args.output_dir / "macro_evidence_summary.json"
    audit.to_csv(audit_path, index=False)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    raw_inputs = []
    for record_id in audit["record_id"]:
        base = args.root / "data" / "raw" / "macro_release_pages" / str(record_id)
        raw_inputs.extend(
            path
            for path in (base.with_suffix(".html"), base.with_suffix(".meta.json"))
            if path.exists()
        )
    manifest = build_run_manifest(
        input_path=args.catalog,
        additional_inputs=[args.evidence, *raw_inputs],
        command=[
            "nrea",
            "macro-evidence-audit",
            "--catalog",
            str(args.catalog),
            "--evidence",
            str(args.evidence),
            "--root",
            str(args.root),
            "--output-dir",
            str(args.output_dir),
        ],
        parameters={
            "catalog_records": len(audit),
            "evidence_matching": "normalized_exact_substring",
            "etf_returns_read": False,
            "regime_thresholds_constructed": False,
        },
        outputs=[audit_path, summary_path],
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "macro_evidence_run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(audit.to_string(index=False))
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return (
        0
        if summary["macro_evidence_gate"] == "pass_current_page_evidence_only"
        else 1
    )


def run_macro_template_audit(args: argparse.Namespace) -> int:
    catalog = pd.read_csv(args.catalog, dtype=str, keep_default_na=False)
    audit, summary = audit_template_drift(args.root, catalog)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = args.output_dir / "macro_template_drift_audit.csv"
    summary_path = args.output_dir / "macro_template_drift_summary.json"
    audit.to_csv(audit_path, index=False)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    raw_inputs = [
        args.root
        / "data"
        / "raw"
        / "macro_release_pages"
        / f"{record_id}.html"
        for record_id in audit["record_id"]
    ]
    manifest = build_run_manifest(
        input_path=args.catalog,
        additional_inputs=raw_inputs,
        command=[
            "nrea",
            "macro-template-audit",
            "--catalog",
            str(args.catalog),
            "--root",
            str(args.root),
            "--output-dir",
            str(args.output_dir),
        ],
        parameters={
            "required_source_families": ["nbs_pmi", "nbs_cpi", "pbc_m2"],
            "required_anchors_per_family": 3,
            "etf_returns_read": False,
            "regime_thresholds_constructed": False,
        },
        outputs=[audit_path, summary_path],
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "macro_template_drift_run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(audit.to_string(index=False))
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return 0 if summary["template_drift_gate"] == "pass" else 1


def run_macro_catalog_discovery(args: argparse.Namespace) -> int:
    discovery = MacroCatalogDiscovery(attempts=args.attempts)
    pages = discovery.fetch_indexes(DEFAULT_INDEX_URLS)
    catalog, candidates, summary = build_coverage_catalog(
        pages, start=args.start, end=args.end
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = args.output_dir / "macro_monthly_source_catalog.csv"
    candidates_path = args.output_dir / "macro_discovery_candidates.csv"
    summary_path = args.output_dir / "macro_catalog_discovery_summary.json"
    catalog.to_csv(catalog_path, index=False)
    candidates.to_csv(candidates_path, index=False)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    archived_inputs = archive_index_pages(pages, args.output_dir)
    manifest = build_run_manifest(
        input_path=archived_inputs[-1],
        additional_inputs=archived_inputs[:-1],
        command=[
            "nrea",
            "macro-catalog-discovery",
            "--start",
            args.start,
            "--end",
            args.end,
            "--output-dir",
            str(args.output_dir),
        ],
        parameters={
            "index_urls": DEFAULT_INDEX_URLS,
            "minimum_family_coverage": 0.95,
            "etf_returns_read": False,
            "regime_thresholds_constructed": False,
        },
        outputs=[catalog_path, candidates_path, summary_path],
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "macro_catalog_discovery_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return 0 if summary["catalog_discovery_gate"] == "pass" else 1


def run_macro_catalog_backfill(args: argparse.Namespace) -> int:
    catalog = pd.read_csv(args.catalog, dtype=str, keep_default_na=False)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    response_dir = args.output_dir / "search_responses"
    backfill = NbsSearchBackfill(
        attempts=args.attempts, max_pages=args.max_pages
    )
    updated, audit, summary = backfill.backfill(
        catalog, response_dir=response_dir
    )
    catalog_path = args.output_dir / "macro_monthly_source_catalog_backfilled.csv"
    audit_path = args.output_dir / "macro_catalog_backfill_audit.csv"
    summary_path = args.output_dir / "macro_catalog_backfill_summary.json"
    updated.to_csv(catalog_path, index=False)
    audit.to_csv(audit_path, index=False)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    response_paths = sorted(response_dir.glob("*.json"))
    manifest = build_run_manifest(
        input_path=args.catalog,
        additional_inputs=response_paths,
        command=[
            "nrea",
            "macro-catalog-backfill",
            "--catalog",
            str(args.catalog),
            "--output-dir",
            str(args.output_dir),
        ],
        parameters={
            "search_scope": "NBS exact title",
            "allowed_domain": "stats.gov.cn",
            "minimum_family_coverage": 0.95,
            "maximum_search_pages": args.max_pages,
            "etf_returns_read": False,
            "regime_thresholds_constructed": False,
        },
        outputs=[catalog_path, audit_path, summary_path],
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "macro_catalog_backfill_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return 0 if summary["search_backfill_gate"] == "pass" else 1


def run_macro_catalog_apply_seeds(args: argparse.Namespace) -> int:
    catalog = pd.read_csv(args.catalog, dtype=str, keep_default_na=False)
    seeds = pd.read_csv(args.seeds, dtype=str, keep_default_na=False)
    updated, audit, summary = apply_reviewed_seeds(catalog, seeds)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = args.output_dir / "macro_monthly_source_catalog_seeded.csv"
    audit_path = args.output_dir / "macro_catalog_seed_audit.csv"
    summary_path = args.output_dir / "macro_catalog_seed_summary.json"
    updated.to_csv(catalog_path, index=False)
    audit.to_csv(audit_path, index=False)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = build_run_manifest(
        input_path=args.catalog,
        additional_inputs=[args.seeds],
        command=[
            "nrea",
            "macro-catalog-apply-seeds",
            "--catalog",
            str(args.catalog),
            "--seeds",
            str(args.seeds),
            "--output-dir",
            str(args.output_dir),
        ],
        parameters={
            "accepted_status": "pending_article_validation",
            "minimum_family_coverage": 0.95,
            "etf_returns_read": False,
            "regime_thresholds_constructed": False,
        },
        outputs=[catalog_path, audit_path, summary_path],
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "macro_catalog_seed_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return (
        0
        if summary["source_catalog_gate"] == "pass_pending_article_validation"
        else 1
    )


def run_macro_catalog_fetch(args: argparse.Namespace) -> int:
    catalog = pd.read_csv(args.catalog, dtype=str, keep_default_na=False)
    record_ids = None
    if args.record_ids is not None:
        record_ids = [
            item.strip() for item in args.record_ids.split(",") if item.strip()
        ]
        if not record_ids:
            raise ValueError("--record-ids must contain at least one record ID")
    archive = MacroMonthlyArchive(
        args.root,
        attempts=args.attempts,
        inter_record_delay_seconds=args.delay,
    )
    results = archive.fetch_catalog(
        catalog, record_ids=record_ids, refresh=args.refresh
    )
    summary = summarize_fetch(results)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_path = args.output_dir / "macro_catalog_fetch_results.csv"
    summary_path = args.output_dir / "macro_catalog_fetch_summary.json"
    results.to_csv(results_path, index=False)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    command = [
        "nrea",
        "macro-catalog-fetch",
        "--catalog",
        str(args.catalog),
        "--root",
        str(args.root),
        "--attempts",
        str(args.attempts),
        "--delay",
        str(args.delay),
        "--output-dir",
        str(args.output_dir),
    ]
    if args.record_ids is not None:
        command.extend(["--record-ids", args.record_ids])
    if args.refresh:
        command.append("--refresh")
    manifest = build_run_manifest(
        input_path=args.catalog,
        command=command,
        parameters={
            "attempts": args.attempts,
            "inter_record_delay_seconds": args.delay,
            "selected_record_ids": record_ids or "all",
            "refresh": args.refresh,
            "etf_returns_read": False,
            "regime_thresholds_constructed": False,
            "outcome": summary["monthly_catalog_fetch_gate"],
        },
        outputs=[results_path, summary_path],
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "macro_catalog_fetch_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return 0 if summary["monthly_catalog_fetch_gate"] == "pass" else 1


def run_macro_catalog_validate(args: argparse.Namespace) -> int:
    catalog = pd.read_csv(args.catalog, dtype=str, keep_default_na=False)
    audit, summary = audit_monthly_catalog(args.root, catalog)
    ledger = build_article_evidence_ledger(audit)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = args.output_dir / "macro_article_validation_audit.csv"
    ledger_path = args.output_dir / "macro_article_evidence_ledger.csv"
    summary_path = args.output_dir / "macro_article_validation_summary.json"
    audit.to_csv(audit_path, index=False)
    ledger.to_csv(ledger_path, index=False)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    raw_inputs: list[Path] = []
    for record_id in audit.loc[audit["page_cached"], "record_id"]:
        page_path = monthly_cache_path(args.root, str(record_id))
        raw_inputs.extend([page_path, page_path.with_suffix(".meta.json")])
    manifest = build_run_manifest(
        input_path=args.catalog,
        additional_inputs=raw_inputs,
        command=[
            "nrea",
            "macro-catalog-validate",
            "--catalog",
            str(args.catalog),
            "--root",
            str(args.root),
            "--output-dir",
            str(args.output_dir),
        ],
        parameters={
            "minimum_family_coverage": MINIMUM_FAMILY_COVERAGE,
            "required_checks": [
                "official domain",
                "catalog title",
                "statistical period",
                "release timing",
                "headline value",
            ],
            "etf_returns_read": False,
            "regime_thresholds_constructed": False,
            "outcome": summary["article_validation_gate"],
        },
        outputs=[audit_path, ledger_path, summary_path],
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "macro_article_validation_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return 0 if summary["article_validation_gate"] == "pass" else 1


def run_macro_panel(args: argparse.Namespace) -> int:
    ledger = pd.read_csv(args.ledger, dtype=str, keep_default_na=False)
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    result = build_macro_panel(ledger, protocol)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    panel_path = args.output_dir / "macro_monthly_panel.csv"
    counts_path = args.output_dir / "macro_state_counts.csv"
    summary_path = args.output_dir / "macro_panel_summary.json"
    result.panel.to_csv(panel_path, index=False)
    result.state_counts.to_csv(counts_path, index=False)
    summary_path.write_text(
        json.dumps(result.summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = build_run_manifest(
        input_path=args.ledger,
        additional_inputs=[args.protocol],
        command=[
            "nrea",
            "macro-panel",
            "--ledger",
            str(args.ledger),
            "--protocol",
            str(args.protocol),
            "--output-dir",
            str(args.output_dir),
        ],
        parameters={
            "protocol_version": protocol["protocol_version"],
            "minimum_state_observations": protocol[
                "minimum_state_observations"
            ],
            "combined_states_constructed": False,
            "etf_returns_read": False,
            "outcome": result.summary["macro_panel_gate"],
        },
        outputs=[panel_path, counts_path, summary_path],
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "macro_panel_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result.summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return 0 if result.summary["macro_panel_gate"] == "pass" else 1


def run_macro_payoff_protocol_audit(args: argparse.Namespace) -> int:
    protocol = load_payoff_atlas_protocol(args.protocol)
    universe = pd.read_csv(args.universe, dtype={"symbol": str})
    summary = audit_payoff_atlas_protocol(protocol, universe)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / "macro_payoff_protocol_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = build_run_manifest(
        input_path=args.protocol,
        additional_inputs=[args.universe],
        command=[
            "nrea",
            "macro-payoff-protocol-audit",
            "--protocol",
            str(args.protocol),
            "--universe",
            str(args.universe),
            "--output-dir",
            str(args.output_dir),
        ],
        parameters={
            "etf_prices_read": False,
            "portfolio_constructed": False,
            "outcome": summary["payoff_protocol_gate"],
        },
        outputs=[summary_path],
        repository=Path.cwd(),
    )
    manifest_path = args.output_dir / "macro_payoff_protocol_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"output_dir={args.output_dir}")
    return 0 if summary["payoff_protocol_gate"] == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "download":
        return run_download(args)
    if args.command == "audit":
        return run_audit(args)
    if args.command == "compare-providers":
        return run_compare_providers(args)
    if args.command == "build-sample":
        return run_build_sample(args)
    if args.command == "baseline":
        return run_baseline(args)
    if args.command == "attention-reproduction":
        return run_attention(args)
    if args.command == "narrative-fetch":
        return run_narrative_fetch(args)
    if args.command == "narrative-audit":
        return run_narrative_audit(args)
    if args.command == "narrative-extract":
        return run_narrative_extract(args)
    if args.command == "narrative-sections":
        return run_narrative_sections(args)
    if args.command == "narrative-features":
        return run_narrative_features(args)
    if args.command == "narrative-timing":
        return run_narrative_timing(args)
    if args.command == "narrative-diagnostics":
        return run_narrative_diagnostics(args)
    if args.command == "market-relations":
        return run_market_relations(args)
    if args.command == "adjusted-relations":
        return run_adjusted_relations(args)
    if args.command == "macro-release-pilot":
        return run_macro_release_pilot(args)
    if args.command == "macro-evidence-fetch":
        return run_macro_evidence_fetch(args)
    if args.command == "macro-evidence-audit":
        return run_macro_evidence_audit(args)
    if args.command == "macro-template-audit":
        return run_macro_template_audit(args)
    if args.command == "macro-catalog-discovery":
        return run_macro_catalog_discovery(args)
    if args.command == "macro-catalog-backfill":
        return run_macro_catalog_backfill(args)
    if args.command == "macro-catalog-apply-seeds":
        return run_macro_catalog_apply_seeds(args)
    if args.command == "macro-catalog-fetch":
        return run_macro_catalog_fetch(args)
    if args.command == "macro-catalog-validate":
        return run_macro_catalog_validate(args)
    if args.command == "macro-panel":
        return run_macro_panel(args)
    if args.command == "macro-payoff-protocol-audit":
        return run_macro_payoff_protocol_audit(args)
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
