# Handoff

For whoever continues this build (including the orchestrator after a context reset). Read `docs/DECISIONS.md` D-010 to D-014 first.

## State (session 2 start)

- `main` holds: docs layout, `make setup` / `make test`, offline test harness, data contracts (`colex/contracts/`), secret handling (hook, `.gitignore`, log scrub).
- Mode: full autonomy (D-013). Goal: `make demo` runs brief §1.5 end to end.

## How to work

- One branch per task from `main`, small commits, `--no-ff` merge after `make test` is green.
- Helper (untracked): `var/tools/g.sh start|commit|merge`. Commit messages are written to `var/msg/*.txt` and deleted after use.
- Never read or print `.env`. Scratch files only under `var/`.

## Next steps

1. Walking skeleton: feed → triage → impact → FakeNotifier → coder → summary on stubs, behind `make demo`.
2. Replace stubs with real code in the order of brief §1.5.

## Gotchas

- The terminal tool echoes long or multi-line commands back; keep commands short and put scripts in files.
- The editor tool refuses to overwrite an existing file without `old_text`.
- `91e3300` on `main` has a wrong commit message (documented in `docs/TASKS.md`).
