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

## Design notes

- A run is driven by `Engine.drive(run_id)`; it replays completed steps (D-016). Human answers go through `Runtime.deliver_human_answer`.
- Step functions get a `StepContext` (`ctx.config`, `ctx.emit(kind, summary)`) and return JSON-serialisable dicts.
- Editor tool limit: about 6000 characters per file write. Split modules.

## Gotchas

- The terminal tool echoes long or multi-line commands back; keep commands short and put scripts in files.
- The editor tool refuses to overwrite an existing file without `old_text`.
- `91e3300` on `main` has a wrong commit message (documented in `docs/TASKS.md`).
