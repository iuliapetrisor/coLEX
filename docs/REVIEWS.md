# coLEX Reviews

Challenge format (brief §6.3, mandatory):

```
[ID] [Severity: Critical|Major|Minor] [Area] [Reviewer]
Claim: what is wrong
Evidence: file:line, failing test, log excerpt, or official text citation
Proposed fix: concrete change
Builder response: ACCEPT (commit) | REJECT (reason) | DEFER (to stretch, reason)
Orchestrator ruling: ...
```

Critical findings block the gate. Major findings must be fixed or explicitly deferred by the orchestrator. Minor findings are optional.

Independence note (ruling D-010): this build session cannot dispatch a separate Code Breaker. Pre-merge reviews recorded here are labeled `Reviewer: same-session self-review (not independent)`. Independent review happens at each gate, in a fresh session opened by the humans, on the diff since the previous tag. Branches touching the merge lock / GitOps, secrets / `.env` / the pre-commit hook, Slack approver authorization, redaction or the Slack manifest scopes are never merged on a self-review: they wait for a human.

## Pre-merge review log

One line per merged branch: branch, reviewer role, what was checked, result.

- `feat/orchestrator/G0-ORC-01` · docs-only (D-010 condition 1), no Code Breaker pass required · checked: every pre-existing file is a 100% rename except the shared-rules README (the root `README` with §3b replaces the older `roles/README.md`); `slack_manifest.yaml` content and scopes unchanged; no secrets staged · merged.

## Findings

[R-001] [Severity: Minor] [QA / test harness] [Code Breaker. Reviewer: same-session self-review (not independent)]
Claim: The offline guard in `tests/conftest.py` leaves two DNS entry points open: `socket.gethostbyname_ex` and `socket.gethostbyaddr`. A test or library calling them sends a real DNS query during `make test`.
Evidence: `tests/breaker/test_harness_network_block.py::test_all_dns_entry_points_are_blocked` (fails at a7f85ca when run with `--runxfail`: `Left contains 2 more items, first extra item: 'gethostbyname_ex'`).
Proposed fix: block every name-resolution function of the `socket` module in the `_no_network` fixture, not only `getaddrinfo` and `gethostbyname`.
Builder response: pending
Orchestrator ruling: pending
