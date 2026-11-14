# Morning review

Written by the orchestrator while working unattended (D-013). Updated as work lands; the last section says how current it is.

## Security-sensitive merges to review

Merged without a human review, on the full-autonomy ruling. All self-reviewed only.

| Branch | Merge | What to look at |
|---|---|---|
| `feat/sec/G0-SEC-01` | see `git log --merges` on `main` | `.githooks/pre-commit` (token rule of D-011, forbidden paths), `.gitignore`, `colex/guardrails/log_scrub.py`. Two commit messages on this branch overstate their test counts (see `docs/TASKS.md`, session 1). |
| `feat/runtime/G0-RT-03` | "merge G0-RT-03 runtime, config store, LLM client" | `colex/guardrails/redaction.py` (IBAN, CNP, email, phone patterns; what is masked before storage and before model calls), `colex/settings.py::load_env` (the app loads `.env` into its own process environment), `colex/llm/client.py` (the key is read from the environment and sent only in the Authorization header). |
| `feat/reg/G2-REG-03` | "merge G2-REG-03 triage, impact analysis, grounding validator" | `colex/guardrails/injection.py` (untrusted-text wrapper: the nonce is a hash of the content, not random, so cached answers can be reused; detection is a keyword heuristic), `colex/guardrails/validators.py` (what counts as grounded), `colex/agents/impact_dispatch.py` (tool allowlist, locate-before-read). |
| `feat/map/G2-MAP-09` | "merge G2-MAP-09 registers and grounding fixes" | `colex/guardrails/validators.py`: a quote may now carry the "N: " line prefixes of read(); contract reviews need an article about contracts. |
| `feat/slack/G3-SLK-04` | "merge G3-SLK-04 Slack notifier and handlers" | `colex/notify/handlers.py` (`_allowed`: who may decide; dedupe of clicks), `colex/notify/app.py` (tokens read from the environment). Tested with a fake client only. The manifest scopes were not changed. |
| `feat/ui/G3-UI-01` | "merge G3-UI-01 Console, server and kill/restart check" | **The Console has no login**: anyone who can reach it can answer legal questions and approve changes as `console-user`. It binds to 127.0.0.1 (`colex/server.py`, checked: not reachable on the LAN address). `colex/api/actions.py` holds every state-changing route. |
| `feat/qa/G3-QA-05` | "merge G3-QA-05 make eval, results, GitOps ceiling fix" | `colex/gitops/core.py`: agent git now runs only in the sandbox repository or its worktrees, with every ancestor directory as a git ceiling. Before this, a git command run exactly in the state directory would have found the coLEX project repository; no call site did that. |
| `feat/ui/G4-UI-07`, `feat/ui/G4-UI-08`, `feat/ui/G4-UI-09` | "merge G4-UI-07 PayRo demo app", "merge G4-UI-08 one PayRo app", "merge G4-UI-09 PayRo phones" | `payro_app/checkout.py` executes the `payments` code checked out in the sandbox repository in a subprocess: scrubbed environment, no network, **no file-system sandbox**. After a human merges a coLEX branch, that code is model-written. No login, 127.0.0.1 only, two ports. **The screens no longer say that PayRo is fictional** (D-025, asked for by the humans). |
| `feat/coder/G3-COD-01` | "merge G3-COD-01 remediation coder, GitOps, test sandbox" | `colex/gitops/core.py` (git subcommand allowlist; the `reference-transaction` hook text), `colex/testrunner/__init__.py` (environment passed to sandboxed tests, limits, network block), `colex/agents/coder_apply.py` (which files the coder may edit). Check: `tests/security/test_merge_lock.py`, `tests/security/test_runner_sandbox.py`. |

Every merge above was reviewed only by the session that wrote it. None had an independent review.

## How to run the demo

```
make setup                 # once: project .venv, dependencies, enables the pre-commit hook
make test                  # offline, about 15 s
make demo OFFLINE=1        # whole brief §1.5 scenario from recorded model answers, about 5 s, no network
make demo                  # same, calling OpenRouter (answers cached in var/llm_cache; first run 1 to 4 min)
make map                   # build the Company Map and print its statistics
make record                # re-record the offline answers after changing a prompt
make console               # Console at http://127.0.0.1:8000 on the demo state (SLACK=0 to keep Slack off)
make payro                 # fictional PayRo app: sender's phone on :8001, receiver's phone on :8002; fees and rules come from `main` of the sandbox repository
make eval                  # docs/RESULTS.md from the recorded run
make slack-check           # read-only: auth, Socket Mode, channels; posts nothing
bash tests/chaos/kill_restart.sh   # kill -9 and restart check, offline
```

`make demo` runs in the terminal. Human decisions are given by a labelled auto-clicker (first option of every question, "approve" for every review), not by a person. State is written to `var/demo/`.

## What works (measured, not assumed)

- **Feed and triage.** 23 official EU acts (verbatim, hashed, sources in `docs/SOURCES.md`). In the recorded run and the live runs so far, the 3 relevant acts scored 1.00 and the 20 distractors 0.00. Caveat: triage prompt v2 was written after seeing v1 results on these same 23 acts, so this is not an independent measurement.
- **Company Map.** 21 PayRo resources from 6 simulated sources; all 21 match the ground truth on path, owner, ownership source and type; 6 of 6 contracts on counterparty, criticality and missing clauses. Caveat: taxonomy keywords and four per-file rules were tuned on this data.
- **Impact analysis.** A tool loop over the map with a rationale per call, locate-before-read, and a grounding validator. Rejections and dropped items are shown on the timeline.
- **Humans in the loop.** A criticality question pauses one branch; the answer re-plans one contract; other branches are not re-run. Approval never merges.
- **Code agent.** Branch per item, sandboxed tests, revise on failure, change request. In live runs: `fees.yaml` passed first try, `transfer.py` passed after one revision, `incidents.py` passed first try in one run and failed all 3 attempts in another (escalated to engineers, no change request).
- **Registers.** DORA Register of Information (6 rows, CSV) and Obligations Register generated from the map.
- **Durability.** Checkpoint after every step, replay-based resume, idempotent side effects, fork / export / import, versioned config with rollback, audit hash chain. Covered by unit tests. `tests/chaos/kill_restart.sh` (kill -9 while waiting for a human, restart, decide) passed once; it is not part of `make test`.

## What does not work or is weaker than the brief asks

- **The map does not save context on this sandbox.** Measured ratio of context used through the map to the whole corpus: 1.17 to 1.51. The corpus is only about 5,400 tokens, and tool-call overhead is larger than that. The "context savings" pitch claim is not supported by these numbers; a larger corpus is needed to test it.
- **Token use is high.** About 350k to 830k model tokens per relevant act, because the full conversation is resent on every step. Cost stayed low only because the model is cheap: a full live demo cost about $0.15.
- **The impact analyst often stops at its 40-step limit** (visible escalation), and its results vary between live runs. The fee schedule document is not always reported.
- **Slack is unverified against the real workspace.** See the checklist below.
- **Measured quality is moderate** (`docs/RESULTS.md`, one recorded run): 7 of 9 expected impact items found, 7 of 13 reported items expected. The fee schedule document was missed.
- **The Console has no login.** It listens on 127.0.0.1 only.
- Not built: DOCX/PDF ingestion, `regulated_by` links, a live update stream in the Console, the demo script and runbook, 14 of the 15 chaos scenarios, repeated live evaluation runs. No Spec Challenger, Legal-Logic Skeptic or independent Code Breaker review happened.

## What is stubbed, faked or scripted

- `make demo` and all tests use `FakeNotifier`: messages are recorded in the outbox table, not sent anywhere.
- The demo auto-clicker answers every human question. Its "yes" to a criticality question is a script, not a legal judgement.
- Flow tests use a scripted stand-in for the model (`tests/e2e/fakes.py`). They prove the runtime and the guards, not model quality.
- `make demo OFFLINE=1` replays one recorded live run.
- PayRo SRL and all sandbox company data are fabricated. Provider names other than Amazon Web Services are invented.
- The DORA register columns are our own, not the official template. Art. 30 clause detection is a keyword heuristic.
- The pitch numbers in brief §1.1 (Compliance.ai study, Romanian VAT law dates) were not verified. Do not use them until someone finds the primary sources.

## Slack: 5-minute manual smoke checklist

Nothing was posted to the real workspace: the Slack code was tested with a fake client only. `make slack-check` did pass against the real workspace (authenticated, Socket Mode connected, all six channels found). Do this before any demo.

1. Set `routing.approvers.legal` and `routing.approvers.engineer` in `config/colex.yaml` (or the Console Settings) to real Slack member ids (profile → "Copy member ID"). They are empty, so until then every Approve or answer click is refused.
2. `make slack-check`, then `make reset && make console`. The first line it prints must say `Slack: connected (Socket Mode)`. Publish acts from the Console Feed page (http://127.0.0.1:8000/feed).
3. Publish `32024R0886`. Expect notifications in `#product` and `#payments-eng` within a few minutes, with evidence links.
4. Click **Acknowledge** on a notification: the buttons are replaced by "Decision: Acknowledged · by you".
5. Publish `32022R2554`. Expect a question in `#legal` with two buttons. Click as a non-approver: you get a private refusal. Click as a legal approver: the message updates and one new notification appears in `#legal`.
6. In `#payments-eng`, on a review message click **Request changes** and type a comment in the modal: a second review message appears. Click **Approve** on it twice: one decision is recorded.
7. Run `/colex status` and `/colex why i1`.
8. Stop the server during a wait, start it again, then click: the run continues and no message is posted twice.

## Gates

`g0`, `g1` and `g2` are tagged, self-reviewed, with deviations from the exit criteria listed in D-022 and in each tag message (`git tag -n20`). No adversarial tester signed off any gate. G3 and G4 are not passed and not tagged: G3 needs real Slack interaction by people.

## OpenRouter spend

About $0.77 in total for this session (435 paid calls, from the usage figures stored with the cached answers).

## Status line

Final for session 2. `make test`: 268 passed, 1 xfailed. `make demo` and `make demo OFFLINE=1` complete. The scenario
of brief §1.5 runs end to end in the terminal and the Console; steps 4 to 6 of that scenario in real Slack are built
but unproven. State and next steps: `docs/HANDOFF.md`.

## Commit list (session 2, oldest first; this file's own commit is the next one)

- `2d2a73e` sec(sec): ignore secrets and local state, add .env.example and secret scan
- `578dca5` sec(sec): add pre-commit hook blocking secrets and forbidden paths
- `7a09359` sec(sec): mask API keys and Slack tokens in log records
- `477e105` sec(sec): merge G0-SEC-01 secret handling, pre-commit hook, log scrub
- `05c4fc8` docs(decision): D-013 full autonomy ruling, D-011 and D-012 accepted
- `f2002ea` feat(sandbox): add official DORA, IPR and distractor excerpts to the feed
- `befee27` feat(sandbox): merge G1-SBX-02 official legal feed
- `15789ed` feat(runtime): durable runtime, config versions, audit chain, redaction
- `0452bff` feat(llm): OpenRouter client with cache, record/replay, retries, redaction
- `c4273d7` feat(runtime): merge G0-RT-03 runtime, config store, LLM client
- `703a384` feat(runtime): walking skeleton of the full run behind make demo
- `47ce46c` feat(runtime): merge G0-ORC-03 walking skeleton behind make demo
- `469e58f` feat(sandbox): fabricate the PayRo company data with traps and ground truth
- `1de6fac` fix(sandbox): expected topic of transfer.py is Transfer authorisation
- `c62c0c4` feat(sandbox): merge G1-SBX-04 PayRo sandbox data
- `61bdbe6` feat(map): Company Map with hierarchy, facets, cross-links, rollups, tools
- `0be11e9` feat(map): merge G1-MAP-03 Company Map
- `bfbc4d6` feat(reg): real triage and impact analysis with a grounding validator
- `6956d95` feat(reg): merge G2-REG-03 triage, impact analysis, grounding validator
- `d98ba5d` feat(coder): remediation coder with merge lock and sandboxed tests
- `5c40a25` feat(coder): merge G3-COD-01 remediation coder, GitOps, test sandbox
- `92415c1` feat(map): DORA Register of Information, Obligations Register, Legal Vault
- `5c31ba9` fix(reg): stop dropping correct findings and accepting wrong contract reviews
- `6d64f92` feat(map): merge G2-MAP-09 registers and grounding fixes
- `4d84d08` feat(reg): criticality questions pause one branch and re-plan one contract
- `1a3684e` feat(reg): merge G3-REG-06 partial pause and re-plan for questions
- `472853c` test(qa): recorded model answers and an offline end-to-end demo test
- `b52b1e2` test(qa): merge G4-QA-06 recorded answers and offline end-to-end test
- `0e8d374` feat(slack): SlackNotifier, Block Kit messages, interaction handlers, /colex
- `70bbcc0` feat(slack): merge G3-SLK-04 Slack notifier and handlers
- `605cc36` docs(review): morning review draft with measured results and open problems
- `9eccebe` feat(ui): Console, server with resume on start-up, kill/restart check
- `18bc399` feat(ui): merge G3-UI-01 Console, server and kill/restart check
- `fddb49c` fix(sec): agent git can never reach a repository that contains the sandbox
- `7724764` feat(eval): make eval scores a demo run and writes docs/RESULTS.md
- `fc87b56` test(sec): runtime code, prompts and config never mention the hidden data
- `395e2fb` feat(eval): merge G3-QA-05 make eval, results, GitOps ceiling fix
