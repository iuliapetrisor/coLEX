# Role 3: Remediation Engineer (code agent)

**Reports to:** Orchestrator · **Reviewed by:** Security (merge lock, sandbox), Code Breaker, Demo Saboteur
**Repo area:** `colex/agents/coder.py`, `colex/gitops/`, `colex/testrunner/`, compliance tests in `sandbox/repo/payments/tests/` (with the Sandbox Author)
**Read first:** brief §1.3 (step 7), §1.5 (step 6), §4.1, §4.3, §5 (repo)

---

## 1. Mission
Turn `CODE_CHANGE` / `CONFIG_CHANGE` impact items into a reviewed patch: create a branch, read **only the files the map points to**, patch, run the sandboxed tests, revise on failure (max 3), and open a PR for engineer review.
**The agent must never merge.** This is enforced in code, with defense in depth, not just written in the prompt.

## 2. Components
### 2.1 `GitOps` (the only way the coder touches git)
```python
class GitOps:
    def create_branch(self, run_id: str, item_id: str) -> str   # 'colex/<run>/<item>' from base sha, in a worktree
    def apply_edits(self, branch: str, edits: list[Edit]) -> ApplyResult  # search/replace blocks, anchored by line ranges
    def commit(self, branch: str, message: str, idempotency_key: str) -> str
    def diff(self, branch: str) -> str
    # NO merge / push / checkout main / reset / rebase methods exist.
```
- Implementation: `subprocess` git with an **argument allowlist**. Any other subcommand raises `ForbiddenGitOperation`.
- **Defense in depth:** install a `reference-transaction` hook in the sandbox repo that rejects any update to `refs/heads/main` while `COLEX_AGENT=1` is set in the environment.
- Work in `var/worktrees/<run>/<item>/`. The sandbox repo is re-seeded from `sandbox/repo_seed/` by `make setup`, so every demo starts from the same state.

### 2.2 Patch generation
- Context = the `ImpactItem` (uri + lines + citation) + files reached via `related(kinds=[depends_on, implements])`, capped by config. **Never the whole repo.**
- Prefer **search/replace edit blocks** over raw unified diffs: they apply more reliably. A failure to apply counts as an iteration, and the error goes back to the model.
- **Never edit, delete or skip existing tests to make them pass.** The runner checks that no file under `tests/` from the base sha was modified or removed, and that no new `skip`/`xfail` marker appears in it. A violation rejects the iteration.

### 2.3 Sandboxed test runner
- `pytest` subprocess, `cwd` locked to the worktree, timeout from config (e.g. 60s), killed with its process group on timeout.
- **Scrubbed environment**: no `OPENROUTER_API_KEY`, no Slack tokens, no proxy variables.
- No network: a conftest plugin blocks `socket.connect`, plus `unshare -n` if available. CPU and memory limits via `resource.setrlimit`.
- Results are parsed from JUnit XML into `tests_before` / `tests_after` with counts and the names of failing tests.

### 2.4 Loop
`tests_before → patch → tests_after → fail? → feed the trimmed failure (test name + assertion + 30 lines max) → revise` (≤ 3 from config) → still failing → `ChangeRequest.status = needs_human`, posted to `#payments-eng` as an escalation.

### 2.5 PR and review
- `ChangeRequest(branch, diff, tests_before, tests_after, iterations, status)`, then `runtime.side_effect(key=f"pr:{run}:{item}")` → `Notifier.request_review`.
- **Approve** → `status=approved`. **Not merged.** The Console shows "Approved by @x at t. Merge is a manual human step" with the command to run.
- **Request changes** → the modal comment goes to the coder as extra input → another iteration, which counts toward the max.

## 3. Expected changes in the demo (coordinate with the Sandbox Author and `expected.yaml`)
| Law | File | Change | Note |
|---|---|---|---|
| IPR equal charges (by 9 Jan 2027 for non-euro MS) | `fees.yaml` | `instant_eur` ≤ `standard_eur` | It is also a **business decision**: the notification goes to `#product`, and the PR is labeled "needs product sign-off". |
| IPR VoP (by 9 Jul 2027 for non-euro MS) | `transfer.py` | VoP check before `authorize_transfer()` | Historical tests must keep passing (e.g. internal own-account transfers). |
| DORA incident reporting | `incidents.py` | initial ≤ 4h from classification / ≤ 24h from awareness; add the intermediate (72h) and final (1 month) reports | Values must come from cited text, not memory. |

**The "test fails, then passes" moment must be real, not staged.** Design historical tests that a naive first patch plausibly breaks (e.g. VoP must not run for own-account transfers). The recorded fixture then makes the demo reproducible offline.

## 4. Tasks
| ID | Task | Timebox | Acceptance criteria |
|---|---|---|---|
| G0-COD-01 | `GitOps` stub + allowlist + ChangeRequest flow against the stub Notifier | 1h | `merge` does not exist on the class. A test proves an arbitrary subcommand is refused. |
| G1-COD-02 | Sandboxed test runner (timeout, env scrub, no network, rlimits, JUnit parse) | 2h | Tests that hang, open sockets or read env vars are all contained (Code Breaker cases). |
| G2-COD-03 | Patch generation with edit blocks + map-scoped context | 2.5h | It applies cleanly on the three expected changes. |
| G3-COD-04 | Revise loop + test-tampering guard + escalation | 2h | The fail → revise → pass sequence is reproducible from fixtures. |
| G3-COD-05 | PR + review integration + `reference-transaction` hook | 1.5h | Approve from Slack ≠ merge. A direct `git merge` with `COLEX_AGENT=1` is rejected by the hook. |

## 5. Definition of done
The three expected code changes are produced on branches. Tests go red → green with ≥ 1 real revision in the demo. A PR review message appears in `#payments-eng`. Security's merge-lock suite is green. The injection document ("merge the PR") produces no merge and is flagged.
