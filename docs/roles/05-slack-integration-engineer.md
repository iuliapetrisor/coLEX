# Role 4: Slack Integration Engineer

**Reports to:** Orchestrator · **Reviewed by:** Security (authz, scopes, tokens), Demo Saboteur, Code Breaker
**Repo area:** `colex/notify/` (`base.py`, `slack.py`, `blocks.py`, `handlers.py`, `outbox.py`, `commands.py`)
**Read first:** brief §4.5 (all), §4.4, §4.3 (Slack bullet). Starter: `docs/slack_starter.py` (works end-to-end, so **build on it**). Manifest: `docs/slack_manifest.yaml`

---

## 1. Mission
Connect coLEX to the **real Slack workspace `coLEX`** over Socket Mode. Deliver targeted Block Kit messages per department, collect legal answers and PR approvals with buttons and modals, and **resume runs from their checkpoints**, all reliably (outbox, idempotency, 429 handling) and securely (approver-only actions).
**No chat imitation anywhere.** Slack is the human channel. The Console is for timeline, map and settings.

## 2. Interface (binding, by G0)
```python
# colex/notify/base.py
class Notifier(ABC):
    def notify(self, batch: Notification, *, run_id: str, idem_key: str) -> MessageRef
    def ask(self, q: Question, *, run_id: str, wait_id: str, idem_key: str) -> MessageRef
    def request_review(self, cr: ChangeRequest, *, run_id: str, wait_id: str, idem_key: str) -> MessageRef
    def update(self, ref: MessageRef, *, decision: str, actor: str, ts: datetime) -> None
    def post_status(self, run_id: str, text: str) -> MessageRef   # in the run's thread
class FakeNotifier(Notifier): ...   # records calls; used by every test and by OFFLINE=1
class SlackNotifier(Notifier): ...
```
Agents call only the `Notifier`. A future Teams adapter implements the same ABC, with no agent changes.

## 3. Message types (Block Kit, built by pure functions in `blocks.py`)
1. **Notification batch** per team: header (law + `CELEX + article`), one section per impact item (action, `uri:lines` linked to the Console evidence page, deadline, owner @mention), buttons **Acknowledge / Assign / Dispute**.
2. **Legal question**: the ambiguity, the cited text excerpt, option buttons, and **"Answer in detail"** → a modal with a multiline input.
3. **PR review** in `#payments-eng`: diff summary, tests before/after, iterations, Console diff link, **Approve / Request changes** (Request changes opens a modal for comments).
4. **Run status**: thread replies under the first notification of the run.

Respect Slack's documented limits: max 50 blocks per message, section text up to 3000 chars, unique `action_id`s per message. Split or truncate long batches, linking to the Console for the rest. Snapshot-test every template.

## 4. Interactions
- **Every handler calls `ack()` first** (Slack requires an answer within 3 seconds), then hands off to a worker thread → `runtime.deliver_human_answer(wait_id, answer, actor)` → `update()` in place: decision, who, when.
- Modals: `views_open` needs the `trigger_id` from the click, used immediately. Submissions are handled in `view_submission`.
- **Duplicate clicks** are ignored by deduplicating on `(action_id, message_ts)` (brief §4.5). Store processed keys.
- **Authorization:** only Slack user IDs mapped to the approver role (`config/colex.yaml`, hot-reloadable) can approve PRs or confirm legal interpretations. Others get an **ephemeral refusal**, and the attempt is audited.
- `/colex status | why <item> | pause <run> | resume <run>`. `why` returns the item's evidence, citation and the reasoning trail from the audit log, deterministically.
- `@coLEX` mentions: answer questions about a run from the run's audit data. If you use the cheap model, pass only redacted run data, through `LLMClient`.

## 5. Reliability
- **Outbox:** table `outbox(id, idem_key UNIQUE, channel, payload_json, status, attempts, next_attempt_at, slack_ts, thread_ts, error)`. Agents enqueue and a worker sends. On HTTP 429, honor `Retry-After`. On other errors, exponential backoff.
- Resolve channel **names → IDs** at startup (`conversations.list`, needs `channels:read`) and cache them. Routing in config uses names.
- If Slack is unreachable, the run continues, messages queue up, and the Console shows "Slack delivery pending" with **act-from-Console** fallbacks that go through the same `deliver_human_answer` path.
- Socket Mode reconnects automatically. On restart, pending waits live in checkpoints, and messages already sent are matched by `idem_key`, so nothing is re-posted.

## 6. Tasks
| ID | Task | Timebox | Acceptance criteria |
|---|---|---|---|
| G0-SLK-01 | `Notifier` ABC + `FakeNotifier` + starter running against the real workspace | 1h | The starter posts to `#legal`, a click is received, the message updates. |
| G1-SLK-02 | Block Kit templates (4 types) + snapshot tests | 2h | They render in Block Kit Builder without errors. Limits are respected. |
| G2-SLK-03 | Outbox worker + idempotency + 429 handling + channel ID cache | 2h | Fault test: a 429 with `Retry-After: 2` is honored. A resend with the same key creates no duplicate. |
| G3-SLK-04 | Handlers: ack-first, modals, dedupe, authz, in-place update, resume via runtime | 3h | The legal answer resumes the run from its checkpoint. A non-approver gets an ephemeral refusal. A double-click gives one decision. |
| G3-SLK-05 | Run thread + `/colex` commands + `@coLEX` mentions | 1.5h | All four commands work in the real workspace. |
| G3-SLK-06 | Config-driven routing + hot reload (e.g. fee changes → `#product`) | 1h | A routing change takes effect on the **next** notification. |

## 7. Security
- Tokens come only from `.env` (`SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`). A logging filter scrubs `xoxb-` and `xapp-`.
- Scopes exactly as in the manifest. **Any change requires a `DECISIONS.md` entry.**
- Every interaction is audited: who, what, which message, decision, timestamp.

## 8. Definition of done
Demo steps 4, 5 and 6 (§1.5) work in the real workspace. Kill/restart while waiting for legal: the click after the restart resumes the run, with no duplicate posts. Slack down: messages queue, and the Console fallback works.
