# Role 4b: Console UI Engineer

**Reports to:** Orchestrator · **Reviewed by:** Spec Challenger ("first 30 seconds"), Demo Saboteur, Code Breaker
**Repo area:** `colex/ui/` (templates, static), `colex/api/` (FastAPI routes + SSE)
**Read first:** brief §2 (Slack vs Console), §3.5, §4.1, §4.4, §1.5 (steps 2, 3, 7, 8), §7

---

## 1. Mission
Build the **coLEX Console**: the place where judges *see the agent think*. It shows the live timeline of decisions with reasoning, evidence, cost and checkpoints, plus the map explorer, registers, PR diff, Settings and the final summary.
**It is not a chat app and must never look like one.** Human conversation happens in Slack.

**Stack recommendation:** FastAPI + server-rendered templates + HTMX/vanilla JS + SSE for live updates. No build step and no SPA framework, unless someone on the team ships React faster.

## 2. Pages
| Page | Must show | Demo step |
|---|---|---|
| **Feed** | Acts in `feed/`, a **"Publish"** button for the presenter (copies a prepared excerpt into the feed), the triage verdict and **why rejected** per act | 2–3 |
| **Run timeline** (landing page) | Live step list: agent, node, **one-line rationale** (map descent), tool called, tokens, cost, duration, **checkpoint marker** on every step, status per branch (running / waiting_for_legal / waiting_for_review / failed / done), **Pause / Resume**, **Fork from here**, export checkpoint | all |
| **Map explorer** | L0→L5 tree with rollups, facet filters, breadcrumbs, primary + secondary memberships, cross-links, an **"inferred"** badge on inferred owners, the Unclassified queue (human assigns → new rule), the counterparty registry review queue | 3, pitch |
| **Evidence viewer** | `/evidence?uri=&start=&end=&map_version=` → source text with the cited lines highlighted. Every claim in the UI links here or to the law article view. | all |
| **Law article view** | Official text by `CELEX + article`, source link, **FICTIONAL – DEMO ONLY** banner if applicable | all |
| **Registers** | Obligations Register (status, owner, deadline), Legal Vault, **DORA Register of Information** with CSV download and clause-gap highlighting | 7 |
| **PR diff** | Branch, unified diff (server-rendered, simple CSS), tests before/after, iterations, review status, "merge is a manual human step" | 6 |
| **Slack delivery** | Outbox status, "Slack delivery pending" banner, **act-from-Console** fallback buttons (same backend path as Slack) | resilience |
| **Settings** | Edit `colex.yaml` (schema-validated form or YAML editor with validation errors), version history, diff between versions, **one-click rollback**, author. Changes apply to the **next** steps. | 4.4 |
| **Summary** | Elapsed time, law → first notification, law → PR, tokens and cost by model, resources touched, **context tokens with the map vs the naive baselines (ratio)**, navigation depth, fragments read / total | 8 |

## 3. API (agree with Runtime and Map at G0; stubs first)
`GET /api/runs`, `GET /api/runs/{id}`, `GET /api/runs/{id}/events` (SSE), `POST /api/runs/{id}/pause|resume`, `POST /api/checkpoints/{id}/fork`, `GET /api/checkpoints/{id}/export`, `POST /api/checkpoints/import`, `GET /api/map/...` (proxies to the map tools, including `unclassified`), `POST /api/map/unclassified/{uri}/assign`, `GET /api/registers/{obligations|dora|vault}`, `GET /api/registers/dora.csv`, `GET /api/changes/{id}`, `GET/POST /api/config`, `POST /api/config/rollback/{version}`, `GET /api/outbox`, `POST /api/feed/publish`, `GET /api/summary/{run}`.

## 4. Design principles (from the rubric)
- **First 30 seconds:** the landing page shows a run in progress with readable reasoning lines, e.g. *"Art. 30 concerns ICT contracts → Legal & Compliance › Contracts › ICT provider contracts"*, not raw JSON.
- **Every claim is clickable** to evidence or a citation. No orphan claims.
- **Visible state for every step** (color plus text label, not color alone).
- **Human control is obvious:** pause, resume, fork, approve or act from the Console when Slack is down, and edit or dispute an impact item.
- Large, readable fonts for projection. Test at 1280×720.
- Sandbox resources show a small "FICTIONAL PayRo data" tag.

## 5. Tasks
| ID | Task | Timebox | Acceptance criteria |
|---|---|---|---|
| G0-UI-01 | FastAPI app skeleton, routes stubbed with fixtures, base layout, SSE plumbing | 1.5h | `make demo` opens the Console and shows the stub run live. |
| G1-UI-02 | Map explorer + evidence viewer + law article view | 3h | Navigable on the real map. Breadcrumbs everywhere. |
| G2-UI-03 | Run timeline with rationales, checkpoint markers, branch states, pause/resume | 3h | Updates live during a real run. |
| G3-UI-04 | Fork / export / import UI, Settings with history/diff/rollback | 2.5h | Demo: change routing → the next notification goes elsewhere → rollback works. |
| G3-UI-05 | Registers + DORA CSV + PR diff + Slack delivery + Console fallback actions | 3h | The fallback approve resumes the run exactly like the Slack approve. |
| G4-UI-06 | Summary page + screenshot polish | 1.5h | Numbers match `RESULTS.md` for the same run. |

## 6. Definition of done
Every §1.5 step except the Slack-native ones is visible in the Console. No page imitates chat. Screenshots for the submission are taken from the real run.
