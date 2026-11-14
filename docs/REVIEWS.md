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
- `feat/qa/G0-QA-01` · Code Breaker, same-session self-review (not independent) · checked: every DNS and socket entry point of the offline guard, the C-level socket type, that `make test` uses the project `.venv` while a foreign virtualenv is active, test collection scope · findings R-001 (Minor, fixed), R-002 (Minor, deferred) · not in the D-010 condition 4 areas.

## Findings

[R-001] [Severity: Minor] [QA / test harness] [Code Breaker. Reviewer: same-session self-review (not independent)]
Claim: The offline guard in `tests/conftest.py` leaves two DNS entry points open: `socket.gethostbyname_ex` and `socket.gethostbyaddr`. A test or library calling them sends a real DNS query during `make test`.
Evidence: `tests/breaker/test_harness_network_block.py::test_all_dns_entry_points_are_blocked` (fails at a7f85ca when run with `--runxfail`: `Left contains 2 more items, first extra item: 'gethostbyname_ex'`).
Proposed fix: block every name-resolution function of the `socket` module in the `_no_network` fixture, not only `getaddrinfo` and `gethostbyname`.
Builder response: ACCEPT (eb2bf96). The guard blocks `getaddrinfo`, `gethostbyname`, `gethostbyname_ex`, `gethostbyaddr` and `getnameinfo`; the xfail marker is removed in the same commit.
Orchestrator ruling: Fixed. Confirmed by re-running the breaker test at eb2bf96: it passes.

[R-002] [Severity: Minor] [QA / test harness] [Code Breaker. Reviewer: same-session self-review (not independent)]
Claim: The offline guard patches `socket.socket`, but not the C-level base type `_socket.socket`. Code that instantiates `_socket.socket` directly can still connect during `make test`. Subprocesses started by tests are not covered either.
Evidence: `tests/breaker/test_harness_c_socket.py::test_c_level_socket_connect_is_blocked` (strict xfail). Probe at a7f85ca: `_socket.socket.connect is _blocked` is False, and patching it raises `TypeError: cannot set 'connect' attribute of immutable type '_socket.socket'`.
Proposed fix: an in-process patch is impossible. Run the test process in a network namespace (`unshare -n`) where the host allows it, together with the sandboxed test runner (G1-COD-02).
Builder response: DEFER. No code in the repo uses `_socket` directly; the limit is documented in the `tests/conftest.py` docstring.
Orchestrator ruling: Deferred to G1-COD-02 (network namespace for test subprocesses). Stays open; the strict-xfail test remains as the reminder.
