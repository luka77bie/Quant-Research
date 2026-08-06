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
from narrative_regime.narrative.archive import (
    NarrativeArchive,
    audit_archive,
    coverage_summary,
)
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
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
