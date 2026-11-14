# coLEX Task Board

Row format: `| ID | Title | Owner | Gate | Status | Notes |`. Status: done / partial / todo.
Rules: `docs/roles/README.md` (§3b). Decisions: `docs/DECISIONS.md`. Findings: `docs/REVIEWS.md`. State and next steps: `docs/HANDOFF.md`.
All work was done by one session playing every role; every review was a self-review (D-010, D-013).

| ID | Title | Owner | Gate | Status | Notes |
|---|---|---|---|---|---|
| G0-ORC-01..03 | Layout, data contracts, skeleton | Orchestrator | G0 | done | Contracts v2 (D-012, D-020) |
| G0-QA-01 | Test layout, offline harness, FakeNotifier, `make setup/test` | QA | G0 | done | R-002 open (Minor) |
| G0-QA-02 | Contract tests + schema snapshots | QA | G0 | partial | Contract tests exist; no JSON-schema snapshots |
| G0-SEC-01 | Secret handling, pre-commit hook, log scrub | Security | G0 | done | |
| G0-RT-01..05 | Model IDs, SQLite, runtime, config store, LLM client | Runtime | G0 | done | D-015, D-016. ADK spike not done (D-003) |
| G0-MAP-01/02 | Connectors, tool schemas, taxonomy | Map | G0 | done | |
| G0-REG-01, G0-COD-01, G0-UI-01, G0-SBX-01 | Agent stubs, GitOps, API skeleton, ground-truth schema | various | G0 | done | Superseded by the real implementations |
| G0-SLK-01 | Notifier interface + starter against the real workspace | Slack | G0 | partial | Interface done. The starter was not re-run; `make slack-check` verified auth, Socket Mode and channels |
| G0-REV-01 | Spec Challenger G0 review | Spec Challenger | G0 | todo | No Spec Challenger review was done at any gate |
| G1-SBX-02/03 | Official excerpts, distractors, `SOURCES.md` | Sandbox | G1 | done | 23 acts. No Legal-Logic Skeptic review |
| G1-SBX-04/05 | PayRo data with traps, seed repository | Sandbox | G1 | done | Markdown and YAML only (D-018) |
| G1-MAP-03..07 | Normalizers, hierarchy, facets, links, rollups, tools | Map | G1 | done | No DOCX/PDF; no `regulated_by` links; L3 by keywords (D-019) |
| G1-SEC-02/03 | Redaction, tool allowlist, read guard | Security | G1 | done | Unit-tested; redaction was not measured on the captured prompts of a full run |
| G1-RT-06..08 | Idempotent side effects, budgets, retries | Runtime | G1 | partial | Built; no `kill -9` subprocess test of side effects, no budget test |
| G1-QA-03 | Guard tests | QA | G1 | partial | Network block, secrets scan, static hidden-data check. No file-access patching during a run |
| G2-REG-02..05 | Watcher, triage, impact loop, grounding | Reg Intel | G2 | done | Quality limits in `docs/RESULTS.md` |
| G2-MAP-08..10 | Obligations Register, DORA register, context metrics | Map | G2 | done | Register columns are our own. Context ratio is above 1 |
| G2-SEC-04..06 | Untrusted wrapper, injection detection, audit chain | Security | G2 | partial | One planted injection payload (a Jira comment) instead of the five in the role file |
| G2-RT-09..11 | Hot reload, fork/export/import, cost accounting | Runtime | G2 | done | |
| G2-QA-04 | Integration tests per agent with cassettes | QA | G2 | partial | One offline end-to-end test and scripted flow tests; no per-agent cassette tests |
| G3-REG-06/07 | Questions, partial pause, re-plan, routing | Reg Intel | G3 | done | General (non-criticality) questions still re-plan through the model |
| G3-COD-02..05 | Test runner, patches, revise loop, review, merge hook | Remediation | G3 | done | Convergence varies between live runs |
| G3-SLK-02..06 | Block Kit, outbox, handlers, commands, routing | Slack | G3 | partial | Built and tested with a fake client. **Never exercised in the real workspace** |
| G3-UI-02..05 | Console pages, fork, settings, registers, diff, fallback | Console | G3 | partial | All pages and the fallback actions exist. No login; page refresh instead of a live stream; the JSON API covers runs and events only, not the full list in the role file |
| G3-QA-05 | Eval harness + `RESULTS.md` | QA | G3 | done | One recorded run |
| G3-SEC-07/08 | Merge-lock suite, Slack authorization tests | Security | G3 | done | Slack part with a fake client |
| G4-QA-06 | Offline end-to-end test, resilience tests | QA | G4 | partial | Offline test done. One chaos script (`tests/chaos/kill_restart.sh`), run once |
| G4-UI-06, G4-SEC-09 | Summary page, export scan, `SECURITY.md` | UI / Security | G4 | partial | Summary and `SECURITY.md` done; no scan of exports and cassettes beyond the token and sample-PII grep |
| G4-UI-07, G4-UI-08 | PayRo demo app: one app that runs the code checked out on `main` of the sandbox repository, so it behaves differently after a human merge (D-023, D-024) | Console | G4 | done | Added in session 3 on request, then reworked: the first, side-by-side version looked staged. 5 tests. Not looked at in a browser by the orchestrator |
| G4-SBX-06, chaos S1–S15, runbook | Demo script, chaos matrix, demo runbook | Sandbox / Saboteur | G4 | todo | Only S3(b) was scripted |
| G5 | Screenshots, video, pitch, one-pager | humans | G5 | todo | |

## Gates

- **g0, g1, g2**: tagged, self-reviewed only.
- **G3 not passed**: its first criterion is real Slack (notifications, a legal answer and a PR approval from Slack). That needs people in the workspace.
- **G4 not passed**: needs G3, three chaos rehearsals and the remaining chaos scenarios.

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
G0 is not ready: 18 of 20 G0 tasks are not done (2 done, 1 doing, 1 blocked, 16 todo).

- **Correction:** two commit messages on the unmerged branch `feat/sec/G0-SEC-01` overstate their test results. `2d2a73e` and `578dca5` both say "make test: 34 passed, 1 xfailed". That was the result on the working tree, which still held files committed later. Tested alone in a clean worktree: `2d2a73e` gives 11 passed, 1 xfailed; `578dca5` gives 24 passed, 1 xfailed; only the branch head `7a09359` gives 34 passed, 1 xfailed. `578dca5` also says "14 hook tests"; there are 13. The commits were already pushed, so they are not amended (§3b). Since then the orchestrator's commit command tests exactly the staged tree.

### Session 2 (2026-11-14, full autonomy, D-013)

Merged to `main` (each after `make test` was green; all self-reviewed): official feed, runtime + config + LLM client,
walking skeleton, PayRo sandbox, Company Map, triage + impact + grounding, coder + GitOps + test sandbox, registers,
question re-plan, recorded answers + offline test, Slack code, Console + server, eval. The full commit list is in
`docs/MORNING_REVIEW.md`. Findings fixed in this session are described in the commit bodies (they were not filed in
`docs/REVIEWS.md`, which stops at R-006). Open: R-002.
