# Morning review

Written by the orchestrator while working unattended (D-013). Updated as work lands; the last section says how current it is.

## Security-sensitive merges to review

Merged without a human review, on the full-autonomy ruling. All self-reviewed only.

| Branch | Merge | What to look at |
|---|---|---|
| `feat/sec/G0-SEC-01` | see `git log --merges` on `main` | `.githooks/pre-commit` (token rule of D-011, forbidden paths), `.gitignore`, `colex/guardrails/log_scrub.py`. Two commit messages on this branch overstate their test counts (see `docs/TASKS.md`, session 1). |
| `feat/runtime/G0-RT-03` | "merge G0-RT-03 runtime, config store, LLM client" | `colex/guardrails/redaction.py` (IBAN, CNP, email, phone patterns; what is masked before storage and before model calls), `colex/settings.py::load_env` (the app loads `.env` into its own process environment), `colex/llm/client.py` (the key is read from the environment and sent only in the Authorization header). |
| `feat/reg/G2-REG-03` | "merge G2-REG-03 triage, impact analysis, grounding validator" | `colex/guardrails/injection.py` (untrusted-text wrapper: the nonce is a hash of the content, not random, so cached answers can be reused; detection is a keyword heuristic), `colex/guardrails/validators.py` (what counts as grounded), `colex/agents/impact_dispatch.py` (tool allowlist, locate-before-read). |

## Status

Work in progress. Sections "what works", "how to run the demo", "what is stubbed or faked", "Slack smoke checklist" and "commit list" are filled in as the build advances.
