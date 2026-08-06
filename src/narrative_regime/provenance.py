from __future__ import annotations

import hashlib
import platform
import subprocess
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_run_manifest(
    *,
    input_path: Path,
    parameters: dict[str, object],
    command: list[str],
    outputs: list[Path],
    repository: Path,
    additional_inputs: list[Path] | None = None,
) -> dict[str, object]:
    commit, dirty = _git_state(repository)
    now = datetime.now(timezone.utc)
    return {
        "run_id": now.strftime("%Y%m%dT%H%M%SZ"),
        "recorded_at_utc": now.isoformat(),
        "code": {"commit": commit, "dirty": dirty},
        "environment": {
            "python": platform.python_version(),
            "pandas": _package_version("pandas"),
            "pypdf": _package_version("pypdf"),
            "project": _package_version("narrative-regime-etf-allocation"),
        },
        "input": {
            "path": str(input_path.resolve()),
            "sha256": sha256_file(input_path),
        },
        "additional_inputs": [
            {"path": str(path.resolve()), "sha256": sha256_file(path)}
            for path in (additional_inputs or [])
        ],
        "command": command,
        "parameters": parameters,
        "outputs": [
            {"path": str(path.resolve()), "sha256": sha256_file(path)}
            for path in outputs
        ],
    }


def _git_state(repository: Path) -> tuple[str | None, bool | None]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        return commit, bool(status.strip())
    except (OSError, subprocess.CalledProcessError):
        return None, None


def _package_version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return None
