# Handoff

For whoever continues this build (including the orchestrator after a context reset). Read `docs/DECISIONS.md` D-010 to D-014 first.

## State (session 2 start)

- `main` holds: docs layout, `make setup` / `make test`, offline test harness, data contracts (`colex/contracts/`), secret handling (hook, `.gitignore`, log scrub).
- Mode: full autonomy (D-013). Goal: `make demo` runs brief §1.5 end to end.

## How to work

- One branch per task from `main`, small commits, `--no-ff` merge after `make test` is green.
- Helper (untracked): `var/tools/g.sh start|commit|merge`. Commit messages are written to `var/msg/*.txt` and deleted after use.
- Never read or print `.env`. Scratch files only under `var/`.

## State (after the walking skeleton)

- `make demo` runs feed → triage → impact → notify → coder → review → verify on the real runtime. It finds DORA (32022R2554), its incident-reporting act (32025R0301) and IPR (32024R0886) relevant and archives 20 acts.
- Real: `colex/runtime/` (steps, checkpoints, waits, side effects, fork/export/import), `colex/config.py`, `colex/llm/` (OpenRouter verified with `openai/gpt-4.1-mini`), watcher, run driver (`colex/agents/flow*.py`, `engine.py`), liaison routing, outbox + FakeNotifier, verifier, redaction, audit chain, official feed in `sandbox/feed/`.
- Stubs, labelled in the timeline: `agents/triage.py` (keywords only), `agents/impact.py` (one fixed item), `agents/coder.py` (no patch), `agents/registers.py` (nothing).
- Not started: PayRo sandbox data, Company Map, Slack implementation, Console, eval.

## Next steps (order of brief §1.5)

1. PayRo sandbox (`sandbox/onedrive|gdrive|confluence|jira|intranet|repo_seed`) with traps and `_ground_truth/expected.yaml`.
2. Company Map: connectors, build, tools (reuse `docs/company_map_starter.py` ideas), then real impact analysis as a tool loop.
3. Triage with the cheap model. 4. Slack notifier (Block Kit, Socket Mode handlers). 5. Coder with GitOps and sandboxed tests.
6. DORA register. 7. Console (FastAPI). 8. Cassettes for `OFFLINE=1`, eval, `docs/MORNING_REVIEW.md`.

## State (after the Company Map, session 2)

- Done and merged: official feed, PayRo sandbox + ground truth, Company Map (`colex/map/`, `make map`, 21/21 resources match ground truth), runtime, LLM client, walking skeleton.
- Still stubs: triage (keywords only), impact, coder, registers. Not started: Slack implementation, Console, eval, cassettes.
- Planned design for the remaining work (follow it unless it proves wrong):
  - Triage: deterministic profile facts + one cheap-model call returning JSON; borderline band asks #compliance.
  - Impact: tool loop over the map tools; every call needs a `rationale`; outputs go through `report_impact` / `ask_legal` / `finish` tools; a grounding validator rejects items whose quote is not verbatim in the cited lines, whose article is unknown, or whose deadline is not a date in the cited article. Owner comes from the map card, never from the model.
  - `wrap_untrusted` nonce must be derived from the content (hash), not random, or the LLM cache and cassettes never hit.
  - LLM cache must live outside the demo state dir (file cache under `var/llm_cache/`); cassettes in `tests/fixtures/llm/` are the committed copy (`make record`).
  - Coder: `GitOps` with a git subcommand allowlist and a `reference-transaction` hook on the sandbox repo; one JSON edit-block answer per iteration; sandboxed pytest; success = relevant tests pass and nothing that passed before fails; tests/ edits rejected.
  - Registers: DORA register CSV from the map; gaps the analyst did not report become items.
  - Slack: `SlackNotifier(OutboxNotifier)`, Block Kit builders, Socket Mode handlers calling `Runtime.deliver_human_answer`.
  - Console: FastAPI, server-rendered; act-from-Console uses the same `deliver_human_answer`.

## State (after the offline demo, session 2) — READ THIS FIRST

- `make demo` (live, cached) and `make demo OFFLINE=1` (recorded answers) both run brief §1.5 end to end in the terminal with FakeNotifier and a labelled auto-clicker. `make test`: 254 passed, 1 xfailed.
- Real and merged: feed, sandbox, map, runtime, LLM client, triage, impact loop + grounding validator, coder + GitOps merge lock + sandboxed tests, DORA register, Obligations Register, question → partial pause → re-plan, recorded cassettes (`make record`).
- NOT built yet: `SlackNotifier` and Socket Mode handlers (only the `Notifier` interface, outbox and `FakeNotifier` exist in `colex/notify/base.py`), the Console (FastAPI), `make eval` + `docs/RESULTS.md`, `SECURITY.md`, product README, final `docs/MORNING_REVIEW.md` sections, `docs/TASKS.md` refresh, gate tags.
- Known quality problems (all visible on the timeline, none hidden): the context ratio is above 1 on this 21-file sandbox (the map does not save context here); the impact analyst often hits its 40-step limit; results vary between live runs (the coder sometimes fails to converge on `incidents.py`); the fee schedule document is not always reported; triage prompt v2 was tuned on the same 23 acts it is measured on.
- After any prompt or tool-output change: run `make demo` live, then `make record`, or the offline test fails on a missing cassette.

## State at the end of session 2 — THIS SECTION IS CURRENT, the ones above are history

- Built since the section above: Slack code (`colex/notify/`), Console + server (`colex/api/`, `colex/server.py`,
  `make console`), `make eval` + `docs/RESULTS.md`, `SECURITY.md`, product `README.md`, `tests/chaos/kill_restart.sh`.
- `make test`: 268 passed, 1 xfailed. Tags g0, g1, g2. Task board: `docs/TASKS.md`. For the humans: `docs/MORNING_REVIEW.md`.
- Next, in order of value: (1) humans run the Slack checklist in `docs/MORNING_REVIEW.md`; fix what it finds.
  (2) Impact quality: the analyst resends the whole conversation each step (350k to 830k tokens per act) and often
  hits its 40-step limit; trimming old tool results from the message list is the obvious fix. (3) A larger sandbox,
  to test whether the map saves context at all. (4) The other chaos scenarios, demo script, runbook.
- After changing a prompt or any text the model sees: `make demo`, then `make record`, or the offline test fails.

## Design notes

- A run is driven by `Engine.drive(run_id)`; it replays completed steps (D-016). Human answers go through `Runtime.deliver_human_answer`.
- Step functions get a `StepContext` (`ctx.config`, `ctx.emit(kind, summary)`) and return JSON-serialisable dicts.
- Editor tool limit: about 6000 characters per file write. Split modules.

## Gotchas

- The terminal tool echoes long or multi-line commands back; keep commands short and put scripts in files.
- The editor tool refuses to overwrite an existing file without `old_text`.
- `91e3300` on `main` has a wrong commit message (documented in `docs/TASKS.md`).
