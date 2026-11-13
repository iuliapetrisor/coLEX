# Role 2: Regulatory Intelligence Engineer

**Reports to:** Orchestrator · **Reviewed by:** Legal-Logic Skeptic, Spec Challenger, Security
**Repo area:** `colex/agents/watcher.py`, `triage.py`, `impact.py`, `liaison.py` (planning part), `prompts/`
**Read first:** brief §1.3–§1.5, §3.5 (navigation protocol), §4, §4.1, §4.3 (grounding), §4.2

---

## 1. Mission
You build the agent's "brain": the Watcher ingests the legal feed, Triage decides relevance **for PayRo** and explains each rejection, and the Impact Analyst navigates the Company Map step by step, picking each next query based on the last result, and produces grounded `ImpactItem`s.
**This is where the judges decide "agent vs fixed workflow".** Every decision must be visible, justified and driven by intermediate results.

## 2. Components and contracts

### 2.1 Watcher
- Polls `sandbox/feed/` every few seconds (no heavy dependencies). Deduplicates acts by CELEX number and content hash, so publishing the same act twice does not create two runs.
- Parses the metadata header (CELEX, title, source URL, publication date, language) and splits the text into articles and paragraphs (`Article N`, `Articolul N`, `N.`, `(a)`) → `LawDocument` / `LawArticle`.
- Extracts effective dates **deterministically first** (regex for dates and "shall apply from"). An LLM fallback is allowed only if it returns a citation to the exact sentence.
- A malformed file is quarantined with a visible reason. It never crashes the loop.

### 2.2 Triage (cheap model + deterministic profile matching)
1. Deterministic scope matching against the **Company Profile** (licence = payment institution, BNR, RON + EUR, transfers, no crypto, EU/RO jurisdictions): addressee terms, sector keywords, CELEX sector.
2. Cheap model call with **only** the profile, the title, the scope/definitions articles and the recitals summary. Never the full act.
3. Output `TriageResult(relevant, articles_flagged[], reason, confidence, matched_profile_facts[])`.
4. **Agentic behaviors:**
   - Confidence in the borderline band (set in config) → a `Question` to `#compliance` instead of a guess.
   - Rejected acts are archived with a reason. The Console shows "why not" for each one.
   - For relevant acts, flag the **exact articles** that create obligations for this entity type.

### 2.3 Impact Analyst (strong model, tool-calling loop over map tools)
- The tool allowlist is exactly the map tools (minus `unclassified`). It is enforced in the dispatcher, not the prompt.
- **Every tool call must carry a one-line `rationale` argument**, e.g. *"Art. 30 concerns ICT contracts → Legal & Compliance › Contracts › ICT provider contracts"*. The dispatcher rejects calls without one. Rationales are emitted as timeline events.
- The prompt enforces the navigation protocol (§3.5): `overview → choose L1 → browse with facets → list_resources → find/search under → read cited lines only → related/counterparty sideways`.
- **Intermediate results drive the next step** (show at least these in the demo):
  - provider found in a contract → `counterparty()` → code modules calling it → `read` those lines;
  - fee entity found in the fee schedule → `related(kinds=[implements])` → `fees.yaml` key;
  - incident procedure says "24h" → `find(deadline)` in code → `incidents.py:INITIAL_REPORT_HOURS`.
- Stop conditions: no unexplored candidate nodes left, the step budget is reached, or the model declares it is done. Budget exhaustion is escalated, never silently truncated.
- Output: `ImpactItem[]` → the **grounding validator** (with Security). Rejected items go back to the model **with the validator error** (max N retries), then are dropped and logged with their reason.
- **Missing information:** an ambiguous article or an unknown contract field (e.g. "does this vendor support a critical or important function?") → a `Question(to_team="legal", options=[...], blocking_items=[...])`. **Only those branches pause.**
- **Change:** when the answer arrives, re-plan **only the affected items** (`blocking_items` ∪ items reachable via `related()`), as a new step with a link to the answer.

### 2.4 Liaison (planning half; Slack Eng renders it)
Group items by `owner_team` → `Notification` batches with concrete to-dos, deadlines, evidence and citations. Routing comes from config. A resource with an unknown owner goes to `#compliance` with an "owner unknown" flag.

## 3. Prompts
- `prompts/<agent>/v<N>.md` with front matter (`id`, `version`, `model_role`, `changelog`). The active version is selected in config, so Settings can switch it.
- Untrusted content (law text, documents) is **always** passed through `wrap_untrusted()` (Security). The system prompt says the content inside is data and its instructions must be ignored.
- Responses are structured (JSON schema / Pydantic). Free-text parsing is not allowed.

## 4. Grounding rules (with Security)
- Citation format: `CELEX:32022R2554 Art. 30(2)(b)`. The validator checks that the article exists in the stored `LawDocument`, and that any quoted text is a **verbatim substring** of it.
- Evidence: `uri` exists in the run's `map_version_id`, and `lines` are within bounds and non-empty.
- A deadline must point either to a cited sentence in the law or to a config value. Never to model memory.

## 5. Tasks
| ID | Task | Timebox | Acceptance criteria |
|---|---|---|---|
| G0-REG-01 | Agent stubs on top of `Runtime.step` + prompt file skeletons | 1h | A stub run goes through every node. |
| G1-REG-02 | Watcher: parse, split, dedupe, dates, quarantine | 2h | Both real excerpts parse into the correct article IDs (checked by the Skeptic). |
| G2-REG-03 | Triage with profile matching + borderline escalation | 2h | On the labeled feed: **recall = 100%** on the relevant acts and precision ≥ 90%. Each rejection has a reason. |
| G2-REG-04 | Impact Analyst loop + rationale-enforced dispatcher + timeline events | 4h | Impact recall ≥ 85% against `expected.yaml`. The DORA and IPR traces visibly follow **different** paths. |
| G2-REG-05 | Grounding validator integration + retry with feedback | 1.5h | 0 ungrounded items reach Liaison (test with injected bad items). |
| G3-REG-06 | Questions + partial pause + re-plan of affected items only | 2h | Test: an answer to Q1 re-runs exactly the expected subset and leaves the other branches untouched. |
| G3-REG-07 | Liaison batching + owner-unknown routing | 1h | Routing accuracy = 100% against `expected.yaml`. |

## 6. Pitfalls
- Do not let the model "remember" DORA. Every legal statement must come from the stored text.
- Do not dump `list_resources` of a whole L1 into context. Filter by facets first.
- Hard-coding the navigation path for the demo laws is **cheating the rubric**. The Spec Challenger will test with a third law, swapped from the feed.

## 7. Definition of done
Both demo laws produce grounded impact items with visible reasoning paths. Triage explains every rejection. A legal answer pauses and resumes exactly the right branches. All prompts are versioned.
