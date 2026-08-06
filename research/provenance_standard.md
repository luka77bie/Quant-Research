# Experiment Provenance Standard v0.1

Every reported table or figure must be traceable through this chain:

```text
provider response -> validated cache -> data manifest -> experiment config
-> raw result -> reporting script -> table or figure
```

## Required result ledger fields

| Field | Requirement |
| --- | --- |
| Run ID | Unique timestamp or deterministic experiment identifier |
| Code | Git commit and dirty-worktree status |
| Config | Complete committed configuration file |
| Data | Provider, symbol set, observed coverage, checksum, and retrieval time |
| Environment | Python and dependency versions |
| Evaluation | Split boundaries, costs, execution delay, and benchmark definitions |
| Processing | Script that produces each reported table and figure |

A result is `verified` only when another run can locate every item above.
Results copied from chat, screenshots, or unsaved notebook state are
`ambiguous` and cannot support a headline claim.
