# Role 7: Security Engineer

**Reports to:** Orchestrator · **Reviews:** Runtime (LLM client, checkpoints), Remediation (merge lock, test runner), Slack (authz, scopes), Map (`read` path safety)
**Repo area:** `colex/guardrails/` (`redaction.py`, `injection.py`, `validators.py`, `budgets.py`, `merge_lock.py`, `allowlist.py`, `audit_integrity.py`), `tests/security/`, `SECURITY.md`
**Read first:** brief §4.3 (all), §4.4 (checkpoint/config secrecy), §4.5 (Slack security), §9 ("no path exists to merge")

---

## 1. Mission
Make coLEX **safe to hand to a regulated company**: no secret or PII leaves the machine un-redacted, untrusted documents cannot steer the agent, the agent cannot merge or write to sources, only mapped humans can approve, budgets cannot run away, and the audit trail can be trusted. **Prove each property with a test.**

## 2. Threat model (short; keep it in `SECURITY.md`)
| Asset | Threat | Control | Proof |
|---|---|---|---|
| API keys / Slack tokens | leak to LLM, logs, checkpoints, git | `.env` only; log scrubbing filter; env scrubbed for subprocesses; secret scan | `test_secrets_never_leave` |
| PII (IBAN, CNP, email, phone) | sent to the LLM; stored in checkpoints/exports | `redact()` in `LLMClient` before every call; reversible map stored locally only; checkpoints and cassettes store redacted data | `test_redaction_*`, export bundle scan |
| `main` branch of the sandbox repo | agent merges | no merge method in `GitOps`; argument allowlist; `reference-transaction` hook; no shell for LLM agents | `test_merge_impossible_*` |
| Document sources | agent writes | connectors without write methods; read-only mount/permissions | `test_connectors_readonly` |
| Agent behavior | prompt injection via laws/docs/tickets/code comments | `wrap_untrusted()` with per-call random delimiters; system instruction; **tool allowlist enforced in the dispatcher**; output validator; suspicious-instruction detector flags the source | `test_injection_*` |
| Approvals | non-approver approves; replayed clicks | approver role mapping; ephemeral refusal; dedupe on (action_id, message_ts); audit | `test_slack_authz`, `test_double_click` |
| Cost | runaway loops | `Budget` (tokens/run, cost/law, iterations/loop) → escalate | `test_budget_escalates` |
| Audit trail | silent tampering | hash chain: each `AuditEvent` stores `prev_hash`; `python -m colex.audit verify` | `test_audit_chain` |
| Map `read()` | path traversal to `.env` | resolve only map URIs, no fs paths | `test_read_traversal` |
| Test runner | network, secrets, hangs | env scrub, socket block, `unshare -n` if available, timeout + process-group kill, rlimits | `test_runner_sandbox` |

## 3. Components (interfaces by G0, real by G2)
```python
redact(text: str, ctx: RedactionCtx) -> str          # IBAN (incl. spaced RO format), CNP (checksum), email, phone → ⟨IBAN_1⟩...
unredact(text: str, ctx: RedactionCtx) -> str        # display-only, never in prompts/checkpoints
wrap_untrusted(doc_id: str, text: str) -> str        # <untrusted id=.. nonce=8f3a..> ... </untrusted nonce=8f3a..>; escapes collisions
detect_injection(text: str) -> list[Finding]         # heuristics: "ignore previous", "you are now", tool names, "merge", etc. → flag, never block silently
validate_grounding(items, law_store, map_version) -> (accepted, rejected_with_reason)
class Budget: check(run_id, kind, amount) -> None | raises BudgetExceeded
ALLOWLIST: dict[agent_name, set[tool_name]]          # dispatcher refuses anything else
```

## 4. Injection test pack (`tests/security/injection/`)
Plant payloads (with the Sandbox Author) in: a contract annex, a Jira comment, a code comment in `providers.py`, a law excerpt marked **FICTIONAL – DEMO ONLY**, and a Slack `@coLEX` mention. Each test asserts:
- no merge, no write, no tool outside the allowlist;
- no extra Slack message and no changed routing;
- the payload source is flagged "suspicious instructions found" in the timeline;
- the normal impact analysis still completes.

## 5. Tasks
| ID | Task | Timebox | Acceptance criteria |
|---|---|---|---|
| G0-SEC-01 | `.gitignore`, `.env.example`, secret-scan test, logging scrub filter, guardrail stubs | 1h | No secret patterns in the repo. Tokens are masked in logs. |
| G1-SEC-02 | Redaction (IBAN, CNP with checksum, email, phone) + reversible map + hook in `LLMClient` | 2h | 100% of seeded PII redacted in the captured prompts of a full run. |
| G1-SEC-03 | Tool allowlist in the dispatcher + `read()` traversal guard | 1h | Calls outside the allowlist are refused and audited. |
| G2-SEC-04 | `wrap_untrusted` + `detect_injection` + injection test pack | 2.5h | All injection tests green. |
| G2-SEC-05 | Grounding validator (with Reg Intel) | 1.5h | Ungrounded claims never reach Liaison. |
| G2-SEC-06 | Budgets (with Runtime) + audit hash chain + verify CLI | 1.5h | A tampered row is detected. |
| G3-SEC-07 | Merge-lock suite + test-runner sandbox review | 1.5h | Every merge path is refused, including a direct `git merge` under `COLEX_AGENT=1`. |
| G3-SEC-08 | Slack authz + dedupe tests; scope review against the manifest | 1h | A non-approver is refused. A replay is ignored. |
| G4-SEC-09 | Checkpoint/export/cassette scan for PII and secrets; `SECURITY.md` (1 page for judges) | 1.5h | The scan is clean. SECURITY.md lists every control with its test name. |

## 6. Definition of done
Every row of §2 has a passing test. `SECURITY.md` maps each guardrail of brief §4.3 to code + test. The Demo Saboteur's injected-document scenario passes.
