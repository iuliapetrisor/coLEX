# coLEX Task Board

Row format: `| ID | Title | Owner | Gate | Timebox | Status (todo/doing/blocked/review/done) | Acceptance link |`
Commit hashes for a finished task are listed at the end of its Acceptance cell.
Rules: `docs/roles/README.md` (§3b commit policy). Decisions: `docs/DECISIONS.md`. Findings: `docs/REVIEWS.md`.

## G0 Contracts & skeleton

Exit criteria: `docs/roles/README.md` §4, row G0. Signs off: Orchestrator + Spec Challenger.

| ID | Title | Owner | Gate | Timebox | Status | Acceptance link |
|---|---|---|---|---|---|---|
| G0-ORC-01 | Repo layout under `docs/`, decision log, task board, review log | Orchestrator | G0 | 45m | done | D-008, D-009, D-010; D-011 still open · commits: ee9dd58, fd19ad9 · merge b112651 |
| G0-ORC-02 | Data contracts: every brief §4.2 model in `colex/contracts/` + `CONTRACTS_VERSION` | Orchestrator | G0 | 1.5h | done | brief §4.2; README §2 rule 2; D-012 · 74 passed, 1 xfailed · R-003 to R-006 fixed · commits: cfe6601, 8a79b5b, 6692fe5, 937f1f6, b09a333, 5e00cf7, 96b418a, 4e5bf46, 13295f6 · merge aa1f8ab |
| G0-ORC-03 | Repo skeleton (brief §8): package dirs; interface stubs land with each owner's G0 task | Orchestrator | G0 | 30m | todo | brief §8 |
| G0-QA-01 | Test layout, `conftest.py` (socket block, tmp DB, FakeNotifier), `make setup`, `make test` | QA | G0 | 1.5h | doing | `docs/roles/08-qa-engineer.md` §6 · merged so far: `make setup`, `make test`, socket block, tmp DB path (6 passed, 1 xfailed) · **still missing: FakeNotifier**, which needs the `Notifier` ABC from G0-SLK-01 · R-001 fixed, R-002 deferred · commits: a7f85ca, 20c662e, ce0a5a9, eb2bf96, d7b66ca, 12f721f · merge 2741fe3 |
| G0-QA-02 | Contract tests for every §4.2 model + schema snapshots | QA | G0 | 1h | todo | `docs/roles/08-qa-engineer.md` §6 |
| G0-SEC-01 | `.gitignore`, `.env.example`, pre-commit hook, secret-scan test, logging scrub filter, guardrail stubs | Security | G0 | 1h | blocked | `docs/roles/09-security-engineer.md` §5 · **needs: human review of branch `feat/sec/G0-SEC-01` before merge** (D-010 condition 4) and a ruling on D-011 · pushed, not merged: `.gitignore`, `.env.example`, secret-scan test, pre-commit hook, log scrub filter (34 passed, 1 xfailed on the branch) · **still missing: guardrail stubs** (redact, wrap_untrusted, validate_grounding, Budget, allowlist) · the hook is not enabled in any clone yet · commits: 2d2a73e, 578dca5, 7a09359 |
| G0-RT-01 | Verify OpenRouter model IDs (`/models`, `tools` support) + `python -m colex.llm.smoke` | Runtime | G0 | 30m | todo | `docs/roles/01-runtime-platform-engineer.md` §5 |
| G0-RT-02 | SQLite schema + numbered migrations, WAL, `busy_timeout` | Runtime | G0 | 45m | todo | `docs/roles/01-runtime-platform-engineer.md` §5 |
| G0-RT-03 | `Runtime` real `start_run/step/checkpoint` + `resume_all` | Runtime | G0 | 1.5h | todo | `docs/roles/01-runtime-platform-engineer.md` §5 |
| G0-RT-04 | `ConfigStore` + `config/colex.yaml` schema | Runtime | G0 | 1h | todo | `docs/roles/01-runtime-platform-engineer.md` §5 |
| G0-RT-05 | `LLMClient` with response cache, record and strict replay modes | Runtime | G0 | 1.5h | todo | `docs/roles/01-runtime-platform-engineer.md` §5 |
| G0-RT-opt | ADK + LiteLLM spike (optional, only if G0 is green) | Runtime | G0 | 30m | todo | D-003 |
| G0-MAP-01 | Connector base + 6 sandbox connectors (list only) + map tool stubs + tool JSON schemas | Map | G0 | 2h | todo | `docs/roles/02-ingestion-map-engineer.md` §4 |
| G0-MAP-02 | `config/taxonomy.yaml` L1–L3 for PayRo | Map | G0 | 45m | todo | `docs/roles/02-ingestion-map-engineer.md` §4 |
| G0-REG-01 | Agent stubs on `Runtime.step` + prompt file skeletons | Reg Intel | G0 | 1h | todo | `docs/roles/03-regulatory-intelligence-engineer.md` §5 |
| G0-COD-01 | `GitOps` stub + argument allowlist + ChangeRequest flow against the stub Notifier | Remediation | G0 | 1h | todo | `docs/roles/04-remediation-engineer.md` §4 |
| G0-SLK-01 | `Notifier` ABC + `FakeNotifier` + starter run against the real workspace | Slack | G0 | 1h | todo | `docs/roles/05-slack-integration-engineer.md` §6 |
| G0-UI-01 | FastAPI skeleton, stub routes, base layout, SSE plumbing | Console UI | G0 | 1.5h | todo | `docs/roles/06-console-ui-engineer.md` §5 |
| G0-SBX-01 | `expected.yaml` schema + resource inventory list | Sandbox | G0 | 1h | todo | `docs/roles/07-sandbox-domain-author.md` §6 |
| G0-REV-01 | Spec Challenger G0 review: check the four seed findings, file what still holds | Spec Challenger | G0 | 45m | todo | `docs/roles/10-spec-challenger.md` §3 |

## G1–G5

Tasks for later gates are defined in the `§Tasks` table of each role file in `docs/roles/`. They are copied onto this board when G0 passes, rescaled to the real hackathon window.

## Session log

New commits per role are reported to the humans at the end of each work session and recorded here.

- 2026-11-14 · **Correction:** commit `91e3300` on `main` carries the wrong message. It repeats the message of merge `2741fe3`, but it is not a merge: it only updates this board (G0-QA-01 progress and commit list, G0-SEC-01 set to doing). Cause: the orchestrator's commit command reused a stale message file. The commit was already pushed, so it is not amended (§3b). Read it as `docs(tasks): record G0-QA-01 progress, start G0-SEC-01`.

### Session 1 (2026-11-14)

One session did every role's work (D-010). All Code Breaker passes were same-session self-reviews, not independent.

Merged to `main`:
- Orchestrator · `feat/orchestrator/G0-ORC-01` · merge b112651 · ee9dd58, fd19ad9
- QA · `feat/qa/G0-QA-01` · merge 2741fe3 · a7f85ca, 20c662e, ce0a5a9, eb2bf96, d7b66ca, 12f721f
- Orchestrator · `feat/orchestrator/G0-ORC-02` · merge aa1f8ab · cfe6601, 8a79b5b, 6692fe5, 937f1f6, b09a333, 5e00cf7, 96b418a, 4e5bf46, 13295f6
- Orchestrator, docs directly on `main` · 96a3b94, 91e3300 (wrong message, see the correction above), f99f2d0

Pushed, waiting for human review (not merged):
- Security · `feat/sec/G0-SEC-01` · 2d2a73e, 578dca5, 7a09359

Self-review findings: R-001, R-003, R-004, R-005, R-006 fixed and confirmed. Open: R-002 (Minor, deferred to G1-COD-02).
Open decisions: D-011 (secret grep versus documentation that quotes token prefixes).
G0 is not ready: 16 of 20 G0 tasks are not done.
