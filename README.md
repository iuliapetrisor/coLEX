# coLEX

Regulatory-change agent prototype for the UiPath Future Forward Hackathon 2026 ("Agents in Action").

**Status: prototype.** The scenario runs end to end in the terminal and the Console. Real Slack is built but has not been exercised in the workspace. Read `docs/MORNING_REVIEW.md` for what works and what does not, and `docs/RESULTS.md` for measured numbers.

## What it does

coLEX watches a feed of official EU acts for a (fictional) Romanian payment institution, PayRo SRL. For each act it decides whether the act concerns the company and says why. For a relevant act it navigates a **Company Map** of contracts, terms, fee schedules, procedures, tickets and code, reports each place that must change with evidence (resource + lines) and a citation (CELEX + article), routes it to the owning team, asks legal when a needed fact is unknown, and opens a code change on a branch for an engineer to review. It never merges. It is decision support for a legal team, not legal advice.

## Run it

```
make setup            # project .venv and dependencies
make test             # offline
make demo OFFLINE=1   # the whole scenario from recorded model answers, no network
make demo             # same with OpenRouter (needs OPENROUTER_API_KEY in .env; see .env.example)
make console          # Console on http://127.0.0.1:8000 over the demo state (no login: local use only)
make payro            # fictional PayRo app, two phones: sender on http://127.0.0.1:8001, receiver on :8002
make eval             # score the recorded run against the ground truth → docs/RESULTS.md
make scale            # Company Map at 21 to 5,021 resources, offline, no model → docs/SCALE.md
make scale-live       # CALLS OPENROUTER: one act analysed at 21, 1,021 and 5,021 resources (one run each)
make scale-console    # second Console on http://127.0.0.1:8003 over the 5,021-resource company of scale-live
make slack-check      # read-only check of the Slack workspace connection
```

In `make demo`, human decisions are given by a labelled auto-clicker. In `make console`, a person decides in the Console, or in Slack once approvers are mapped in Settings.

## How it is built

- **Company Map** (`colex/map/`): a deterministic build from six simulated sources into a hierarchy (company → area → domain → topic → resource → fragment) with facets (type, owner, counterparty, criticality, lifecycle), typed cross-links with evidence, and rollup summaries. Agents reach it only through bounded tools: `overview`, `browse`, `list_resources`, `find`, `search`, `counterparty`, `owners`, `related`, `obligations`, `read`.
- **Agents** (`colex/agents/`): watcher, triage (profile matching plus one small model call), impact analyst (a tool loop over the map), liaison (routing by ownership), coder (branch, patch, sandboxed tests, revise), register step, verifier.
- **Runtime** (`colex/runtime/`): an explicit state machine with a checkpoint after every step, durable human waits per branch, idempotent side effects, resume after restart, fork, export and import, versioned configuration with rollback, and a hash-chained audit trail. SQLite.
- **Guardrails**: see `SECURITY.md`.
- **Humans**: Slack (`colex/notify/`) and the Console (`colex/api/`) share one decision path.

## What the numbers say

From `docs/RESULTS.md`, one recorded run on a 21-resource sandbox: triage 3 of 3 relevant acts and 20 of 20 distractors; 7 of 9 expected impact items found, 7 of 13 reported items expected; routing 7 of 7; three code change requests, none merged. The agent read about as much through the map as the whole corpus contains (ratio 0.99 to 1.54), so **on this small sandbox the map does not save context**. The rules and one prompt were tuned on this same data.

## Sources

Official texts: `docs/SOURCES.md`. The study and the VAT-law dates quoted in the brief were not verified.

- Brief: `docs/PROJECT_BRIEF.md`
- Team rules and commit policy: `docs/roles/README.md` (§3b)
- Task board: `docs/TASKS.md`
- Decisions: `docs/DECISIONS.md`
- Reviews: `docs/REVIEWS.md`

PayRo SRL and all sandbox company data are fictional.
