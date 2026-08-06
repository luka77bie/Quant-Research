# Project Working Rules

## Research integrity

- Treat `research/research_contract.md` as the governing research scope.
- Keep the frozen MOM60 baseline unchanged except for a documented correctness
  fix recorded in `research/decision_log.md`.
- Do not describe a non-empty download as complete without coverage checks.
- Never silently fill, fabricate, forward-fill, or splice missing market data.
- Keep AKShare and Yahoo caches separate until an overlap audit is documented.
- Narrative features require point-in-time publication and retrieval metadata.
- Negative and null results are valid project outcomes.

## Code boundaries

- Put reusable logic under `src/narrative_regime/` and tests under `tests/`.
- Notebooks may explore data but must not contain the only implementation of a
  reported signal, backtest, metric, table, or figure.
- Add abstractions only for current callers and current research requirements.
- Keep provider packages optional; offline tests must not require network calls.
- Do not commit generated data, credentials, machine-local paths, or caches.

## Verification

- Run `python -m pytest` for behavior changes.
- Run `ruff check .` when Ruff is available.
- Record data versions, code commit, config, command, and artifact paths for
  every result used in a report.
- Narrow claims when the benchmark, provenance, or failure evidence is missing.
