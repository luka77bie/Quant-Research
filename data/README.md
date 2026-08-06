# Local Data Layout

```text
raw/<provider>/<symbol>.csv       validated or partial provider cache
raw/<provider>/<symbol>.meta.json coverage, checksum, and retrieval metadata
manifests/downloads.jsonl         append-only provider attempt ledger
manifests/latest_download_summary.csv latest per-symbol operational summary
sample/                           small committed offline fixtures only
```

Raw and generated data are intentionally ignored by Git. Do not commit API
credentials, private licensed data, or machine-specific absolute paths.
