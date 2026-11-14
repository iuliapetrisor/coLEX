# Morning review

Written by the orchestrator while working unattended (D-013). Updated as work lands; the last section says how current it is.

## Security-sensitive merges to review

Merged without a human review, on the full-autonomy ruling. All self-reviewed only.

| Branch | Merge | What to look at |
|---|---|---|
| `feat/sec/G0-SEC-01` | see `git log --merges` on `main` | `.githooks/pre-commit` (token rule of D-011, forbidden paths), `.gitignore`, `colex/guardrails/log_scrub.py`. Two commit messages on this branch overstate their test counts (see `docs/TASKS.md`, session 1). |

## Status

Work in progress. Sections "what works", "how to run the demo", "what is stubbed or faked", "Slack smoke checklist" and "commit list" are filled in as the build advances.
