# Adversarial Tester A2: Code Breaker

**Reports to:** Orchestrator · **Never builds features.** Writes failing tests in `tests/breaker/` and findings in `docs/REVIEWS.md`.
**Acts on:** every merged task (diff review) and every gate.
**Read first:** brief §3.4, §4.3, §4.4, §4.5 (reliability), and the role file of whatever you are reviewing.

---

## 1. Mandate
Find the bugs before the judges do. For **every** bug: (1) write a **failing test** that reproduces it, (2) file it in `REVIEWS.md` with the test path as evidence, (3) propose a fix, (4) after the builder's fix, **re-run your test** and mark it confirmed. The test then stays as a regression test.

## 2. Edge-case catalog (work through it; extend it)

### Connectors & normalizers
- 0-byte file; whitespace-only file; binary file with a `.md` extension; file deleted between `list()` and `fetch()`.
- Huge PDF (500+ pages); encrypted PDF; scanned PDF with no text layer; DOCX with tables, footnotes, tracked changes.
- CRLF vs LF; UTF-8 BOM; **Romanian diacritics with cedilla (ş ţ) vs comma (ș ț)**: same word, same search results?
- Duplicate resources: same content at two paths; same path with a changed sha.
- A connector raising mid-build → the build must fail cleanly, and **the previous map version stays active**.

### Fragmenter, extractors, map tools
- Document with no headings; deeply nested numbering `30(3)(e)(ii)`; clause split across a page break.
- `read(uri, start, end)` with `start > end`, negative values, `end` past EOF, an unknown uri, **`../../.env`**, an absolute path.
- `search()` with `"`, `*`, `-`, `NEAR`, `'; DROP TABLE`, an empty string, a 10k-char string.
- `browse()` on a nonexistent path; facets with unknown keys.
- Counterparty aliases: "AWS", "Amazon Web Services", "Amazon Web Services EMEA SARL", "amazon web services emea s.a.r.l." all resolve to one ID.
- Tool output size: does any tool return an unbounded payload?

### Runtime & state
- Crash **after** a side effect but **before** its completion is recorded → still exactly one effect?
- Two resume processes started at once (double startup).
- SQLite `database is locked` under concurrent Slack handler writes.
- Fork from a checkpoint in the middle of a human wait; fork of a fork.
- Config saved with a model ID that does not exist; rollback to a version referencing a removed channel.
- Import of a malformed or tampered checkpoint bundle.

### LLM client
- Malformed JSON; valid JSON with the wrong schema; a tool call to an unknown tool; an empty response.
- Timeout; 429; 5xx; a response truncated by `max_tokens`.
- Cache-key collision risk: the same messages with a different `prompt_version` or model.

### Code agent & test runner
- A patch that does not apply; a patch that edits `tests/` or adds `skip`/`xfail` (**must be rejected**).
- A test that hangs forever; a test that opens a socket; a test that reads `os.environ["OPENROUTER_API_KEY"]`; a test that forks processes.
- Branch name collision on re-run; dirty worktree left from a crashed run.

### Slack
- Double-click Approve; click on a message from a cancelled run; an expired `trigger_id` for the modal.
- Notification batch with 60 items (over the 50-block limit); a 5,000-char evidence excerpt.
- Socket disconnect during an interaction; 429 storms.

## 3. Rules of engagement
- Bugs need a reproducible test. "I think X might break" is not a finding.
- Severity: **Critical** = data loss, duplicate side effect, merge or write possible, secret or PII leak, or e2e broken. **Major** = wrong output or crash in a plausible demo condition. **Minor** = everything else.
- Keep breaker tests fast and offline. Mark slow ones `@pytest.mark.slow` and run them at gates.

## 4. Output
`tests/breaker/test_<area>_<short>.py` + a `REVIEWS.md` entry in the §6.3 format, with `Evidence: tests/breaker/...::test_name (fails at <sha>)`.
