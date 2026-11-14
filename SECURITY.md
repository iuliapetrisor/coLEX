# coLEX security notes

Every control below was reviewed only by the session that wrote it. There has been no independent security review. PayRo SRL and its data are fictional.

| Guardrail (brief §4.3) | How it is enforced | Test |
|---|---|---|
| Agents cannot merge or move `main` | `GitOps` has no merge, push, checkout, reset, rebase or update-ref; a git subcommand allowlist; a `reference-transaction` hook in the sandbox repository rejects any update of `refs/heads/main` while `COLEX_AGENT=1`; agent git runs only in the sandbox repository and its worktrees. Approval records a decision and never merges. | `tests/security/test_merge_lock.py` |
| Read-only document sources | Connectors have no write method; `read()` resolves map URIs only, never file paths | `tests/unit/test_map.py`, `tests/unit/test_map_tools.py` |
| Tool allowlist per agent | The Impact Analyst's dispatcher refuses any tool that is not a map tool or one of its three reporting tools; every call needs a rationale; `read` needs a prior locate | `tests/unit/test_impact_guards.py` |
| Prompt injection | Law text and documents reach the model wrapped as untrusted data with a content-derived delimiter; lines that look like instructions are flagged on the timeline and in the map review queue. Detection is a keyword heuristic. | `tests/unit/test_impact_guards.py`, `tests/unit/test_map.py` |
| Grounding | An impact item is accepted only if its article exists in the stored law, its quote is verbatim in the cited lines, its deadline is a date written in the cited article and its action fits the resource type. The owner comes from the map, not the model. | `tests/unit/test_impact_guards.py` |
| Secrets | Keys and tokens live in `.env` (git-ignored) and are read from the environment only; a pre-commit hook and a test scan for token-shaped strings; log records are scrubbed; the sandboxed test runner gets a scrubbed environment | `tests/security/test_no_secrets_committed.py`, `test_pre_commit_hook.py`, `test_log_scrub.py`, `test_runner_sandbox.py` |
| Personal data | IBAN, CNP (checksum), e-mail and phone are replaced by placeholders before every model call and masked before anything is stored (checkpoints, audit events, exports, recorded answers) | `tests/security/test_redaction.py`, `tests/unit/test_llm.py`, `tests/unit/test_runtime.py` |
| Sandboxed tests | No network (socket block plus a network namespace where the host allows it), CPU and memory limits, process-group kill on timeout, a parent `pytest.ini` is ignored | `tests/security/test_runner_sandbox.py` |
| Budgets | Token and cost budgets are checked before every step and inside the agent loops; an overrun becomes a question to a human | checked in code; no dedicated test yet |
| Slack approvals | Only Slack users mapped under `routing.approvers` for the role of a request may decide; others get a private refusal; double clicks count once; every interaction is audited | `tests/security/test_slack_authz.py` (fake Slack client) |
| Audit trail | Events form a hash chain; `python -m colex.runtime.audit` verifies it | `tests/unit/test_runtime.py` |
| Hidden evaluation data | Runtime code, prompts and config never reference it; connectors skip every path part starting with `_` | `tests/security/test_hidden_ground_truth.py` |

## Known gaps

- **The Console has no login.** Anyone who can reach it can answer legal questions and approve changes as `console-user`. It listens on 127.0.0.1 only. Do not expose it.
- Slack authorization was tested with a fake client, not in the real workspace. No approver is mapped in `config/colex.yaml`.
- Redaction and injection detection are pattern-based and will miss cases outside their patterns.
- The coder edits files chosen by map links and its tests run with the limits above, but the patch itself is model-written code: an engineer must review it. That is why nothing is merged automatically.
- `side_effect()` retries an effect whose completion record was lost; it relies on each effect being idempotent per key. Two processes driving the same run at once are not locked out.
- The offline guard of `make test` cannot block the C-level socket type (finding R-002, open).
