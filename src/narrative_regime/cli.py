from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from narrative_regime.data.downloader import DownloadManager
from narrative_regime.data.models import FetchRequest
from narrative_regime.data.providers import build_providers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nrea")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="download daily ETF data")
    download.add_argument("--universe", type=Path, required=True)
    download.add_argument("--start", type=date.fromisoformat, required=True)
    download.add_argument("--end", type=date.fromisoformat, required=True)
    download.add_argument("--providers", default="akshare,yahoo")
    download.add_argument("--attempts", type=int, default=3)
    download.add_argument("--delay", type=float, default=1.0)
    download.add_argument("--refresh", action="store_true")
    download.add_argument("--root", type=Path, default=Path.cwd())
    return parser


def run_download(args: argparse.Namespace) -> int:
    universe = pd.read_csv(args.universe, dtype={"symbol": str})
    if "symbol" not in universe:
        raise ValueError("universe file must contain a symbol column")

    provider_names = [item.strip() for item in args.providers.split(",") if item]
    manager = DownloadManager(
        root=args.root,
        providers=build_providers(provider_names),
        attempts=args.attempts,
        inter_symbol_delay_seconds=args.delay,
    )
    if universe["symbol"].duplicated().any():
        duplicates = sorted(universe.loc[universe["symbol"].duplicated(), "symbol"])
        duplicate_text = ", ".join(duplicates)
        raise ValueError(f"universe contains duplicate symbols: {duplicate_text}")

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
        result for result in results if result.status in {"failed", "partial"}
    ]
    print(f"\ncomplete={len(results) - len(incomplete)} incomplete={len(incomplete)}")
    print(f"summary={summary_path}")
    return 1 if incomplete else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "download":
        return run_download(args)
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
