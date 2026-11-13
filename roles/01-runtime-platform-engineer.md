# Role 0: Runtime Platform Engineer

**Reports to:** Orchestrator · **Reviewed by:** Code Breaker, Demo Saboteur, Security
**Repo area:** `colex/runtime/`, `colex/llm/`, `colex/config.py`, `config/colex.yaml` + schema, `colex/contracts/` (persistence side)
**Read first:** brief §2, §4, §4.2, §4.4, §4.3 (budgets), and `README.md` §2–§6

---

## 1. Mission
Build the backbone every other agent plugs into: a durable state machine, the run/step/checkpoint store, resume-on-startup, idempotent side effects, the OpenRouter LLM client with routing, cache and accounting, and versioned, hot-reloadable configuration with fork, export and import.
Your interfaces must be usable as **real implementations, not mocks, by G0**. Every other builder codes against them from hour 3.

## 2. You own / you do not own
| You own | You do not own |
|---|---|
| State machine, `runs/steps/checkpoints/config_versions/audit_events/idempotency_keys/llm_cache` tables | Agent logic inside nodes (Reg Intel, Coder) |
| `LLMClient`: routing, cache, retries, timeouts, token/cost accounting, recorded fixtures | Redaction/injection logic (Security provides it; you call its hooks) |
| `ConfigStore`: schema, versions, diff, hot reload, rollback | Slack outbox worker logic (Slack Eng); you provide the idempotency primitive |
| Fork / export / import of checkpoints | UI for these (Console Eng); you provide the API |

## 3. Interfaces to deliver by G0 (signatures are binding)
```python
# colex/runtime/api.py
class Runtime:
    def start_run(self, law_id: str, *, parent_checkpoint_id: str | None = None) -> Run: ...
    def step(self, run_id: str, branch_id: str, node: str,
             fn: Callable[[StepContext], StepOutput], inputs_ref: str) -> StepOutput:
        """Budget check → snapshot config version → run fn → AuditEvent → checkpoint.
        Retries on transient errors per config; on final failure marks branch 'failed'
        and emits a visible escalation event (never silent)."""
    def side_effect(self, key: str, fn: Callable[[], T]) -> T:
        """Checkpoint BEFORE calling fn; if key already completed, return stored result."""
    def wait_for_human(self, run_id: str, branch_id: str, question: Question | ChangeRequest) -> None
    def deliver_human_answer(self, wait_id: str, answer: dict, actor_user_id: str) -> None  # thread-safe
    def pause(self, run_id: str) -> None; def resume(self, run_id: str) -> None
    def fork(self, checkpoint_id: str, *, config_version_id: str | None = None) -> Run
    def export_checkpoint(self, checkpoint_id: str) -> bytes   # JSON bundle, redacted
    def import_checkpoint(self, bundle: bytes) -> Run
    def resume_all(self) -> list[str]   # called at startup; returns resumed run_ids

# colex/llm/client.py
class LLMClient:
    def complete(self, agent: str, messages: list[dict], *, tools: list[dict] | None = None,
                 response_model: type[BaseModel] | None = None, prompt_version: str,
                 run_id: str | None = None) -> LLMResult  # .content .tool_calls .usage .cost_usd .cached

# colex/config.py
class ConfigStore:
    def active(self) -> ConfigVersion
    def save(self, payload: dict, author: str) -> ConfigVersion   # validates, hashes, diffs, audits
    def rollback(self, version_id: str, author: str) -> ConfigVersion  # creates a NEW version
    def get(self, version_id: str) -> ConfigVersion
    def history(self) -> list[ConfigVersion]
```

## 4. State machine (explicit, no framework magic)
Nodes: `WATCH → TRIAGE → IMPACT → LIAISON → [ASK_LEGAL ⏸] → REMEDIATE → [REVIEW ⏸] → VERIFY → DONE`.
- **Branches:** each `ImpactItem` is one branch with its own status. A paused branch never blocks the others.
- **Loop-backs** (these make the agent visibly agentic):
  - a legal answer → `IMPACT` re-run **only for `blocking_items` plus items reached by `related()` edges**;
  - "Request changes" → `REMEDIATE` (counts toward max iterations);
  - budget exceeded → `ESCALATED ⏸` with a `Question` to `#compliance`.
- The transition table lives in code as data (`TRANSITIONS: dict[node, set[node]]`), so the Console can draw it and tests can assert that illegal transitions raise.
- Run status ∈ `running | waiting_for_legal | waiting_for_review | failed | done | cancelled`. It is derived from the branch statuses.

## 5. Tasks
| ID | Task | Timebox | Acceptance criteria |
|---|---|---|---|
| G0-RT-01 | **Verify OpenRouter model IDs.** Call `GET https://openrouter.ai/api/v1/models`, choose `MODEL_CHEAP` and `MODEL_STRONG`, and check that `supported_parameters` includes `tools` (and `response_format` if you use it). | 30m | `python -m colex.llm.smoke` makes one real call per model and prints tokens and cost. IDs and date go in DECISIONS. Nothing is hard-coded: env vars or config only. |
| G0-RT-02 | SQLite schema + simple numbered migrations, WAL mode, `busy_timeout` | 45m | `make setup` creates the DB. A migration test runs. |
| G0-RT-03 | `Runtime` real implementation of `start_run/step/checkpoint` + `resume_all` | 1.5h | Unit tests: a checkpoint exists after each step. A run resumes from the last checkpoint in a new process. |
| G0-RT-04 | `ConfigStore` + `config/colex.yaml` schema (models per agent, budgets, thresholds, channel routing, connectors, profile overrides, prompt versions, templates) | 1h | An invalid config is rejected with a readable error. Saving produces version, hash, diff and author. |
| G0-RT-05 | `LLMClient` with response cache (key = sha256 of model + messages + tools + params + prompt_version), **record** and **replay** fixture modes (replay is strict: a miss fails the test) | 1.5h | A cached call returns `cached=True` at zero cost. Replay works with the network disabled. |
| G1-RT-06 | `side_effect()` idempotency + checkpoint-before-side-effect | 1h | A kill between the checkpoint and the effect, then a restart, produces exactly one effect (subprocess `kill -9` test). |
| G1-RT-07 | Budgets (tokens per run, cost per law, iterations per loop) using the Security `Budget` primitive | 45m | Exceeding a budget gives `ESCALATED` with a visible event and a `Question`. |
| G1-RT-08 | Timeouts and retries: exponential backoff on 429/5xx/timeout, max attempts from config, then escalate | 45m | Fault-injection test: 2 failures then success, or 4 failures then escalation event. |
| G2-RT-09 | Hot reload: each step snapshots `config_version_id` at its start, so new steps pick up the new version and completed steps never change | 1h | Test: change routing mid-run → the next notification uses the new channel, and the earlier step still shows the old version. |
| G2-RT-10 | Fork / export / import + API endpoints for the Console | 1.5h | Forking from any checkpoint creates a new run with `parent_checkpoint_id` and leaves the original untouched. The exported bundle has no secrets and no un-redacted PII (Security test). |
| G2-RT-11 | Cost accounting per model: use OpenRouter's usage/cost reporting if the response provides it, otherwise the pricing fields from `/models` | 45m | `AuditEvent.cost_usd` is filled. The run summary splits cost by model. |
| G0-RT-opt | ADK + LiteLLM spike (**optional**, only if G0 is already green) | 30m hard | Proof of an e2e call, or a DECISIONS entry saying "not used". |

## 6. Acceptance tests you must ship
- `test_resume_after_kill.py`: start a run in a subprocess, `kill -9` it during `IMPACT`, restart, and verify the run completes with no duplicate side effects.
- `test_idempotent_side_effects.py`: the same key twice produces one effect.
- `test_fork_isolation.py`: a fork never mutates the parent run.
- `test_config_versioning.py`: save, diff, rollback; rollback creates a new version.
- `test_illegal_transition.py`.

## 7. Pitfalls
- **SQLite concurrency:** the Slack Socket Mode handlers run on other threads. Route all writes through one writer queue, or use short transactions with `busy_timeout`. Never share a connection across threads.
- **Checkpoints store references, not blobs:** `state_ref` points to a redacted blob table. Checkpoints must never contain un-redacted PII or secrets.
- **Cache keys must include `prompt_version`**, otherwise a prompt edit silently replays stale answers.
- A human wait has **no timer** that fails the run. It waits durably, and the Console shows its age.

## 8. Definition of done
All of §5 and §6 are green. The Demo Saboteur's "kill the server mid-run" scenario passes 3/3. The Console can draw the state machine from `TRANSITIONS`.
