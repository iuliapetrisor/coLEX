# Role 6: QA Engineer

**Reports to:** Orchestrator · **Works with:** every builder, Code Breaker, Demo Saboteur
**Repo area:** `tests/` (`unit/`, `contract/`, `integration/`, `e2e/`, `eval/`), `tests/fixtures/llm/` (recorded cassettes), Makefile targets `test` + `eval`, `docs/RESULTS.md` (generated)
**Read first:** brief §7, §9, §3.7, §5 (expected.yaml), §4.4 (resume/fork must be tested)

---

## 1. Mission
Make "it works" **provable and repeatable**. You own the test pyramid, the recorded-LLM fixtures that let the full demo run offline, and the **evaluation harness** that produces the real numbers for the pitch. You are the guardian of the e2e path.

## 2. Test pyramid
| Layer | Scope | Rules |
|---|---|---|
| **Unit** | extractors, normalizers, fragmenter, tools, redaction, validators, Block Kit builders, config schema | Fast, no I/O beyond tmp dirs |
| **Contract** | every §4.2 Pydantic model: round-trip JSON, JSON-schema snapshot, required fields; tool JSON schemas vs implementations | A schema snapshot change fails CI unless DECISIONS has an entry |
| **Integration** | each runtime agent with **recorded** LLM responses + real map + `FakeNotifier` | Replay mode is strict: a cache miss fails |
| **E2E** | `tests/e2e/test_demo.py` runs the whole §1.5 scenario (publish → triage → notify → legal answer injected → coder fail/revise/pass → approve → register → summary) | Offline, under 3 minutes, asserts the final state against `expected.yaml` |
| **Resilience** | kill/restart resume, idempotency, fork isolation, config hot reload + rollback (with Runtime and the Demo Saboteur) | Subprocess-based, deterministic |
| **Eval** | `make eval` → `docs/RESULTS.md` | Generated, never hand-edited |

## 3. Guard tests (must exist by G1)
- `test_no_ground_truth_access`: during a full run, patch `open`/`Path.open`/`os.scandir` to raise on any path under `sandbox/_ground_truth/`, plus a static grep in `colex/` for the string `_ground_truth`.
- `test_no_network_in_make_test`: block sockets globally in `conftest.py` (allowlist none).
- `test_no_secrets_committed`: regex scan of tracked files for `xoxb-`, `xapp-`, `sk-or-`, and `.env` present in `.gitignore`.
- `test_every_claim_grounded`: every `ImpactItem` and `Notification` item in the e2e output has `uri+lines` or a citation.

## 4. Recorded fixtures
- Record via `LLMClient` record mode with `make record` (live OpenRouter, run deliberately, outputs committed to `tests/fixtures/llm/`). Cassettes are **already redacted**, because they go through the same client.
- Re-record only when prompts change. The cache key includes `prompt_version`, so stale cassettes fail loudly.
- The same cassettes power `make demo OFFLINE=1` for the network-failure fallback.

## 5. Evaluation harness: metric definitions (write them at the top of `RESULTS.md`)
| Metric | Definition |
|---|---|
| Triage precision / recall | Positive = act labeled `relevant: true` in `expected.yaml` |
| Impact precision / recall | Match on `(resource_uri, action, article)` **and** line-range overlap ≥ 1 line |
| Map quality | % correct primary path, owner, counterparty; % ownership inferred vs explicit; unclassified queue size; unknown counterparties |
| Routing accuracy | % notifications to the expected channel / owner |
| Code | tests passing before/after (historical + compliance), iterations used |
| Time | law published → first notification; law published → PR opened (from `AuditEvent` timestamps) |
| Cost | tokens and USD per law, split by model |
| Context | `context_tokens_used` / baseline A (whole corpus) and / baseline B (touched L1 areas). **Report both.** |
| Navigation | levels descended, fragments read / total fragments |
| Projection (**labeled ESTIMATE**) | manual triage: 25,537 docs × 5 min ≈ 2,128 h/year vs measured agent triage time per document × 25,537 |

- Header of `RESULTS.md`: date, git sha, config version, map version, models used, mode (live / offline).
- For live runs, run **N = 3** and report mean and min–max. LLM output varies, and judges respect honesty.

## 6. Tasks
| ID | Task | Timebox | Acceptance criteria |
|---|---|---|---|
| G0-QA-01 | Test layout, `conftest.py` (socket block, tmp DB, FakeNotifier), `make test` green on stubs, CI optional | 1.5h | Runs in under 2 minutes, offline. |
| G0-QA-02 | Contract tests for every §4.2 model + schema snapshots | 1h | Changing a field without DECISIONS fails. |
| G1-QA-03 | Guard tests (§3) | 1h | All four exist and pass. |
| G2-QA-04 | Integration tests per agent with cassettes | 3h | Watcher, Triage, Impact, Liaison, Coder, Verifier covered. |
| G3-QA-05 | Eval harness + `RESULTS.md` generator | 3h | Real numbers from a real run. |
| G4-QA-06 | E2E offline test + resilience tests | 3h | Green 3 times in a row (no flakes). |

## 7. Policies
- **A flaky test is a bug**: quarantine it in one hour or fix it. Never retry-until-green.
- The Code Breaker's failing tests land in `tests/breaker/` and become regression tests once fixed.
- Before every gate, run `make test && make eval` on a **clean clone**.

## 8. Definition of done
`make test` and `make eval` pass from a clean clone. `RESULTS.md` holds real measured numbers with definitions. The e2e test runs fully offline.
