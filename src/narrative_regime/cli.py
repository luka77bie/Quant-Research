from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from narrative_regime.baseline.momentum import run_momentum_baseline
from narrative_regime.data.audit import audit_provider_cache
from narrative_regime.data.downloader import DownloadManager
from narrative_regime.data.models import FetchRequest
from narrative_regime.data.panel import (
    build_common_sample,
    validate_availability_metadata,
)
from narrative_regime.data.providers import build_providers
from narrative_regime.provenance import build_run_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nrea")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="download daily ETF data")
    download.add_argument("--universe", type=Path, required=True)
    download.add_argument("--start", type=date.fromisoformat, required=True)
    download.add_argument("--end", type=date.fromisoformat, required=True)
    download.add_argument("--providers", default="akshare,yahoo")
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

    sample = subparsers.add_parser(
        "build-sample", help="build an audited single-provider common sample"
    )
    sample.add_argument("--universe", type=Path, required=True)
    sample.add_argument("--availability-sources", type=Path, required=True)
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


def run_build_sample(args: argparse.Namespace) -> int:
    universe = _read_universe(args.universe)
    sources = pd.read_csv(args.availability_sources, dtype={"symbol": str})
    validate_availability_metadata(universe, sources)
    result = build_common_sample(
        root=args.root,
        provider=args.provider,
        universe=universe,
        start=args.start,
        end=args.end,
        reference_symbol=args.reference_symbol,
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
        additional_inputs=[args.availability_sources, *cache_inputs],
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "download":
        return run_download(args)
    if args.command == "audit":
        return run_audit(args)
    if args.command == "build-sample":
        return run_build_sample(args)
    if args.command == "baseline":
        return run_baseline(args)
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
