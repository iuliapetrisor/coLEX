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
- `feat/orchestrator/G0-ORC-02` · Code Breaker, same-session self-review (not independent) · checked: timestamps with and without timezone, ownership consistency, NaN / infinite / negative amounts and their JSON round trip, blank and duplicate list entries, unknown fields, the closed vocabularies · findings R-003, R-004, R-005 (Major, fixed), R-006 (Minor, fixed) · not in the D-010 condition 4 areas; note that `ChangeRequest.status` has no "merged" value, which is a data vocabulary and not the merge lock itself.

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

[R-003] [Severity: Major] [Contracts] [Code Breaker. Reviewer: same-session self-review (not independent)]
Claim: `AuditEvent.ts`, `Checkpoint.ts` and `ConfigVersion.ts` accept timestamps without a timezone. Subtracting one from a timezone-aware timestamp raises `TypeError`, which would break the "law published → first notification" time metric and the timeline ordering.
Evidence: `tests/breaker/test_contracts_edge_cases.py::test_timestamps_without_timezone_are_rejected` (fails at cfe6601 with `--runxfail`). Probe at cfe6601: `TypeError: can't subtract offset-naive and offset-aware datetimes`.
Proposed fix: type the three fields as timezone-aware datetimes.
Builder response: ACCEPT (937f1f6). The three `ts` fields are timezone-aware datetimes. The xfail marker is removed in the same commit.
Orchestrator ruling: Fixed. Confirmed by re-running the breaker test at 96b418a: it passes.

[R-004] [Severity: Major] [Contracts] [Code Breaker. Reviewer: same-session self-review (not independent)]
Claim: `ResourceCard` accepts contradictory ownership: no owner with `ownership_source="explicit"`, or an owner with `ownership_source="unknown"`. The "owner unknown → #compliance" routing (brief §3.2) depends on these two fields agreeing.
Evidence: `tests/breaker/test_contracts_edge_cases.py::test_ownership_source_must_agree_with_owner_team` (fails at cfe6601 with `--runxfail`).
Proposed fix: a model validator: `owner_team is None` if and only if `ownership_source == "unknown"`.
Builder response: ACCEPT (b09a333). `owner_team` is empty exactly when `ownership_source` is `unknown`. The xfail marker is removed in the same commit.
Orchestrator ruling: Fixed. Confirmed by re-running the breaker test at 96b418a: it passes.

[R-005] [Severity: Major] [Contracts] [Code Breaker. Reviewer: same-session self-review (not independent)]
Claim: `Checkpoint.budgets_used` accepts infinite, NaN and negative values. An infinite value is written to JSON as `null`, and the checkpoint then fails to load: a checkpoint that cannot be resumed from.
Evidence: `tests/breaker/test_contracts_edge_cases.py::test_checkpoint_budgets_must_be_finite_and_non_negative` (fails at cfe6601 with `--runxfail`). Probe at cfe6601: dump then load of a checkpoint with `inf` raises a `float_type` validation error.
Proposed fix: budget values are finite floats ≥ 0.
Builder response: ACCEPT (5e00cf7). Budget values and `cost_usd` are finite and non-negative. The xfail marker is removed in the same commit.
Orchestrator ruling: Fixed. Confirmed by re-running the breaker test at 96b418a: it passes.

[R-006] [Severity: Minor] [Contracts] [Code Breaker. Reviewer: same-session self-review (not independent)]
Claim: `Question.options` accepts blank and duplicate entries, and `Question.blocking_items` accepts blank ids. Options become Slack buttons, which need distinct, non-empty labels and action ids.
Evidence: `tests/breaker/test_contracts_edge_cases.py::test_question_options_and_blocking_items_are_non_blank_and_unique` (fails at cfe6601 with `--runxfail`).
Proposed fix: non-blank elements in both lists and unique options.
Builder response: ACCEPT (96b418a). Options and blocking items are non-blank; options are unique. The xfail marker is removed in the same commit.
Orchestrator ruling: Fixed. Confirmed by re-running the breaker test at 96b418a: it passes.
