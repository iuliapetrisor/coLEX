# coLEX Build Team: Role Briefs

> Issued by the **Orchestrator** (tech lead + PM). Source of truth: `docs/PROJECT_BRIEF.md`.
> Every agent receives three files: `PROJECT_BRIEF.md`, this `README.md` (shared rules), and its own role file.
> If a role file conflicts with the brief, **the brief wins**. Raise the conflict in `docs/DECISIONS.md` through the orchestrator.

---

## 1. Roster

| # | Role | File | Repo area | Main rubric criterion | Main deliverable due at |
|---|---|---|---|---|---|
| 0 | Runtime Platform Engineer | `01-runtime-platform-engineer.md` | `colex/runtime/`, `colex/llm/`, `colex/config.py`, `config/colex.yaml` | Agent design (20), Working result (30) | **G0** (interfaces), G2 (fork/hot reload) |
| 1 | Ingestion & Map Engineer | `02-ingestion-map-engineer.md` | `colex/connectors/`, `colex/map/`, `config/taxonomy.yaml` | Originality (15), Agent design (20) | G1 |
| 2 | Regulatory Intelligence Engineer | `03-regulatory-intelligence-engineer.md` | `colex/agents/{watcher,triage,impact}.py`, `prompts/` | Agent design (20), User value (25) | G2 |
| 3 | Remediation Engineer (code agent) | `04-remediation-engineer.md` | `colex/agents/coder.py`, `colex/gitops/`, `sandbox/repo/` tests | Working result (30), Agent design (20) | G3 |
| 4 | Slack Integration Engineer | `05-slack-integration-engineer.md` | `colex/notify/` | Usability & control (10), User value (25) | G3 |
| 4b | Console UI Engineer | `06-console-ui-engineer.md` | `colex/ui/`, `colex/api/` | Usability & control (10), Working result (30) | G3 |
| 5 | Sandbox & Domain Author | `07-sandbox-domain-author.md` | `sandbox/`, `docs/DEMO_SCRIPT.md` | User value (25) | G1 |
| 6 | QA Engineer | `08-qa-engineer.md` | `tests/`, `Makefile` (test/eval), `docs/RESULTS.md` | Working result (30) | G4 |
| 7 | Security Engineer | `09-security-engineer.md` | `colex/guardrails/`, `SECURITY.md` | Agent design (20), Usability & control (10) | G2 (core), G4 (proof) |
| A1 | Spec Challenger | `10-spec-challenger.md` | `docs/REVIEWS.md` only | All criteria | Every gate |
| A2 | Code Breaker | `11-code-breaker.md` | `tests/breaker/`, `docs/REVIEWS.md` | Working result (30) | Every merged task |
| A3 | Legal-Logic Skeptic | `12-legal-logic-skeptic.md` | `docs/REVIEWS.md`, `docs/LEGAL_CHECKS.md` | User value (25), credibility | G1, G2, G4 |
| A4 | Demo Saboteur | `13-demo-saboteur.md` | `tests/chaos/`, `docs/REVIEWS.md`, `docs/DEMO_RUNBOOK.md` | Working result (30), Agent design (20) | G3, G4 |

---

## 2. Non-negotiable shared rules

1. **The e2e path comes first.** A working `make demo` matters more than any feature. When a task runs 50% over its timebox, the orchestrator cuts or simplifies it.
2. **Data contracts are frozen after G0.** The models in `colex/contracts/` (§4.2 of the brief) change only through a `DECISIONS.md` entry approved by the orchestrator, with `CONTRACTS_VERSION` bumped. Additive optional fields are cheap. Renames and removals are expensive.
3. **Work against stubs.** Never wait on another builder. Every interface exists as a stub at G0 and returns fixture data.
4. **One LLM path.** Every model call goes through `colex.llm.LLMClient`, which handles routing, cache, redaction, accounting and budgets. Direct HTTP calls to OpenRouter anywhere else fail review.
5. **Every agent step goes through the runtime.** `runtime.step(...)` writes the `AuditEvent` and the checkpoint. A step that bypasses it is a bug.
6. **Never invent legal text.** Official text comes only from EUR-Lex or other official sources, stored with its CELEX number and article. Hypothetical acts carry **"FICTIONAL – DEMO ONLY"** on every page.
7. **No merge path.** No code path an agent can reach may merge, push to `main` or write to a document source.
8. **Secrets.** Secrets live only in `.env`, which is git-ignored, and are never logged, checkpointed or sent to an LLM. Check `.env.example` before committing.
9. **Ground truth is hidden.** Runtime code never reads `sandbox/_ground_truth/`. A test enforces this (QA).
10. **Tests ship with code.** `make test` runs offline in under 2 minutes, using recorded LLM fixtures and a fake Slack client.
11. **Evidence everywhere.** Every user-facing claim carries `uri + lines` or `CELEX + article`.

---

## 3. Working conventions

- **Branches:** `feat/<role>/<task-id>`, e.g. `feat/map/G1-MAP-03`. Keep PRs small. The orchestrator merges each one after a Code Breaker pass.
- **Task IDs:** `G<gate>-<AREA>-<nn>`. Areas: `RT` runtime, `MAP`, `REG`, `COD` coder, `SLK` Slack, `UI`, `SBX` sandbox, `QA`, `SEC`.
- **`docs/TASKS.md` row format:**
  `| ID | Title | Owner | Gate | Timebox | Status (todo/doing/blocked/review/done) | Acceptance link |`
- **`docs/DECISIONS.md` entry:** `D-NNN | date | decision | one-line rationale | decided by`
- **`docs/REVIEWS.md` entry:** use the challenge format from brief §6.3 exactly.
- **Blocked for more than 30 minutes?** Set the status to `blocked`, write what you need and from whom, and ping the orchestrator.
- **Timeboxes** below are written as `T+Nh` from kickoff and assume a build window of about 44 hours. The orchestrator rescales them to the real hackathon window at kickoff.

---

## 4. Stage gates

A gate passes only with **zero open Critical findings** in `REVIEWS.md`. Each Major finding must be fixed or explicitly deferred by the orchestrator.

| Gate | Target | Exit criteria | Signs off |
|---|---|---|---|
| **G0 Contracts & skeleton** | T+3h | Repo skeleton (§8 of brief). `colex/contracts/` has every §4.2 model. Every tool, agent, Notifier and API endpoint exists as a stub. SQLite schema and migrations exist. `config/colex.yaml` and its schema load. **OpenRouter model IDs verified** and recorded in DECISIONS. `docs/slack_starter.py` runs against the real workspace. `make setup`, `make test` (stubs) and `make demo` (a stub run) exist and pass. | Orchestrator + Spec Challenger |
| **G1 Map & sandbox** | T+12h | PayRo sandbox complete with traps and `expected.yaml`. Real DORA/IPR excerpts and distractors in `feed/`. Map builds with hierarchy, facets, cross-links and rollups. All §3.5 tools work. First map-quality numbers exist. | + Legal-Logic Skeptic, Code Breaker |
| **G2 Regulatory brain** | T+20h | Watcher → Triage → Impact run on both laws with the grounding validator active. Navigation trace visible as structured events. Triage P/R and impact recall measured. Redaction, injection defenses and budgets wired into `LLMClient`. Checkpoints after every node. Resume-on-startup works. | + Legal-Logic Skeptic, Spec Challenger |
| **G3 Humans & code** | T+30h | Real Slack: notification batches, legal question (buttons + modal) → run resumes from checkpoint, PR review → approval from Slack. Coder loop: fail → revise → pass → PR. Merge lock proven. Console timeline, map explorer, PR diff and Settings live. | + Demo Saboteur, Code Breaker |
| **G4 E2E & resilience (feature freeze)** | T+38h | `make demo` runs §1.5 end to end in under 5 minutes. Kill/restart resumes with no duplicates. Fork works from the UI. A config change applies to the next step and can be rolled back. Offline fixture mode works. `make eval` writes real numbers to `RESULTS.md`. Chaos rehearsal pass rate is 3/3. | All four testers |
| **G5 Submission** | T+44h | README of 2 pages or less, SECURITY.md, one-page description, screenshots, backup video, 5-minute pitch rehearsed twice, repo link. | Orchestrator |

---

## 5. Interface ownership matrix

| Interface | Owner | Main consumers |
|---|---|---|
| `colex/contracts/*` (Pydantic models) | Orchestrator (authored at G0), Runtime (persistence) | everyone |
| `Runtime` API (`start_run`, `step`, `wait_for_human`, `deliver_human_answer`, `side_effect`, `fork`, `resume_all`) | Runtime | all agents, Slack, Console |
| `LLMClient.complete(...)` | Runtime | Reg Intel, Map (L3 classifier, summaries), Coder, Slack (mentions) |
| `ConfigStore` + `config/colex.yaml` schema | Runtime | everyone, Console Settings |
| Map tools (`overview`, `browse`, `list_resources`, `find`, `search`, `counterparty`, `owners`, `related`, `obligations`, `read`) + JSON schemas | Map | Impact Analyst, Coder, Console |
| `Connector` base class | Map | Sandbox (data layout) |
| `Notifier` ABC (`notify`, `ask`, `request_review`, `update`, `post_status`) | Slack | Liaison, Coder, Runtime |
| `GitOps` (allowlisted git operations) | Remediation | Coder only |
| `redact()/unredact()`, `wrap_untrusted()`, `validate_grounding()`, `Budget`, merge-lock tests | Security | LLMClient, Impact, Coder |
| REST/SSE API (`colex/api/`) | Console UI | Console, Slack (deep links) |
| `expected.yaml` schema | Sandbox Author | QA (eval), Legal-Logic Skeptic |

---

## 6. Orchestrator rulings on gaps in the brief

| ID | Gap | Ruling |
|---|---|---|
| D-001 | The §4 diagram names the tool `neighbors`. §3.5 defines `related`. | `related` is canonical. `neighbors` stays as a thin alias, because the starter code uses it. |
| D-002 | §6.1 points to the stage gates in "§7", but §7 is Evaluation. | The gates are defined in §4 of this file. |
| D-003 | Orchestration framework. | Use a plain, explicit Python state machine. The ADK spike is optional: 30 minutes, Runtime Engineer, and only if G0 is already green. |
| D-004 | The DORA Art. 30 checklist mixes Art. 30(2), which applies to all ICT contracts, with Art. 30(3), which applies only to contracts supporting critical or important functions. | The checklist tags each clause with its paragraph. The Legal-Logic Skeptic verifies it against the official text. |
| D-005 | PR target. | A local git branch plus the diff in the Console. A real GitHub PR is a stretch goal. |
| D-006 | LLM mode for the demo. | `make demo` calls OpenRouter live by default. `make demo OFFLINE=1` replays recorded fixtures. `make test` is always offline. |
| D-007 | Rollup summaries. | Deterministic template summaries are the default. The cheap-model polish is optional and cached. This keeps the build reproducible and cheap. |
