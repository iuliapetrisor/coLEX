# Role 1: Ingestion & Map Engineer

**Reports to:** Orchestrator · **Reviewed by:** Code Breaker, Spec Challenger, Legal-Logic Skeptic
**Repo area:** `colex/connectors/`, `colex/map/`, `config/taxonomy.yaml`, `config/map_rules.yaml`
**Read first:** brief §3 (all of it, it is the core of the product), §5, §4.2. Starter: `docs/company_map_starter.py`

---

## 1. Mission
Build the **Company Map**: a six-level hierarchy (L0 Company → L5 Fragment) with facets, typed cross-links and rollups, so the runtime agent **never receives "all documents"**. Also build the Legal Vault, the Obligations Register, the Company Profile and the DORA Register of Information export.
**You must prove the map's value with numbers:** the context-token ratio, navigation depth and routing accuracy.

**Reuse the starter:** its extractors, SQLite + FTS5 storage, import graph and `overview/find/search/neighbors/read/impact`. Add the hierarchy, facets, cross-links and new tools. Do **not** rewrite it.

## 2. Interfaces to deliver (stubs by G0, real by G1)
```python
# colex/connectors/base.py   (read-only by construction: no write methods exist)
class Connector(ABC):
    source: Literal["onedrive","gdrive","confluence","jira","intranet","repo"]
    def list(self) -> Iterable[RawRef]          # uri, path, sha, mime, metadata{owner, space_owner, modified, ...}
    def fetch(self, ref: RawRef) -> RawResource # bytes + metadata; raises ConnectorError (never returns partial silently)

# colex/map/tools.py  (each returns JSON-serializable dict incl. "breadcrumbs" and "map_version_id")
overview() ; browse(path, depth=1, facets={}) ; list_resources(path, facets={})
find(etype, value, under=None) ; search(text, under=None) ; counterparty(name)
owners(team) ; related(uri_or_path, kinds=[]) ; obligations(article=None, path=None)
read(uri, start, end) ; unclassified()   # UI only, NOT in the runtime allowlist
neighbors = related   # alias kept for starter compatibility (D-001)
```
- Export **JSON schemas** for function calling in `colex/map/tool_schemas.py`. These are the only tools the Impact Analyst sees.
- Every tool result is **size-bounded**: max items and max characters set in config, with `next_cursor` for pagination. Each result reports its own `tokens_estimate`, which feeds the context metric.

## 3. Build pipeline (deterministic first, LLM last)
1. **Ingest and normalize** md, txt, docx (`python-docx`), pdf (`pypdf`), html, code, yaml/json, and Confluence/Jira exports to text with **stable 1-based line numbers**.
2. **Fragment** into L5 units: headings and clauses, functions and classes (Python `ast`), and config keys, each with a line range.
3. **Extract signals** with line numbers: `ict_provider, contract_clause, deadline, fee, payment_flow, personal_data, legal_ref, jurisdiction, currency`, plus owner metadata and counterparty mentions.
   - The `contract_clause` checklist lives in `config/dora_art30_checklist.yaml`. Each clause has an `id`, a **paragraph tag** (`30(2)` for all ICT contracts, `30(3)` for contracts supporting critical or important functions; ruling D-004), detection patterns (EN + RO), and an official-text reference. The Legal-Logic Skeptic signs this file off.
4. **Resolve facets** in priority order: explicit metadata, then folder conventions (`config/map_rules.yaml`), then LLM inference marked `ownership_source=inferred`.
5. **Assign the primary path:** rules give L1/L2. The cheap model picks L3 **from the closed taxonomy only** and returns a confidence. Below the threshold, the resource goes to the Unclassified queue. A human assignment is saved as a new rule.
6. **Link counterparties** against the registry (canonical name + aliases; normalize case, diacritics and legal suffixes like SRL, SARL, Ltd, GmbH, Inc). Unknown names go to the review queue. Then attach contract → services → code modules using imports, config endpoints and hostnames.
7. **Create cross-links** (`governed_by, implements, same_counterparty, references, depends_on, same_owner, regulated_by`), each with **evidence (uri + lines)**, plus secondary memberships.
8. **Compute rollups** bottom-up. Summaries are **deterministic templates** (ruling D-007), for example: `ICT provider contracts: 7 · gaps: 3 missing 30(3) audit rights, 2 data location unspecified · owners: legal(6), unknown(1) · contractors: AWS, SMSLink…`. An optional cheap-model polish is cached and regenerated only when a child changes.
9. **Quality gate:** every resource has a primary path, an info type, an owner (or an explicit `unknown`) and a confidence. Expose counts of inferred owners, unclassified resources and unknown counterparties.
10. **Incremental build:** skip resources whose sha is unchanged, remove deleted ones, recompute only the affected rollups. `map_version_id = hash(resource shas + taxonomy version + extractor version)`. A failed build **never becomes the active version**.

## 4. Tasks
| ID | Task | Timebox | Acceptance criteria |
|---|---|---|---|
| G0-MAP-01 | Connector base + 6 sandbox connectors (list only) + tool stubs returning fixtures + tool JSON schemas | 2h | Impact Analyst devs can call every tool against stubs. |
| G0-MAP-02 | `config/taxonomy.yaml` L1–L3 for PayRo (closed vocabulary, versioned with config) | 45m | Covers every expected primary path in `expected.yaml`. |
| G1-MAP-03 | Normalizers + fragmenter + fintech extractors (reuse the starter) | 3h | Unit tests per format, including diacritics (ș/ş, ț/ţ), CRLF, BOM and empty files. |
| G1-MAP-04 | Hierarchy, primary path, unclassified queue, rule learning | 2h | ≥ 90% of primary paths correct against `expected.yaml`. |
| G1-MAP-05 | Facets: ownership (CODEOWNERS, Drive owner, Confluence space owner, header), counterparty registry + aliases, lifecycle, sensitivity | 2.5h | **100% of ICT contracts linked to the correct counterparty**, including the "AWS" ↔ "Amazon Web Services EMEA SARL" trap. The unowned document is flagged `unknown`, never dropped. |
| G1-MAP-06 | Cross-links + secondary memberships + rollups | 2h | `related("repo://payments/fees.yaml")` shows its secondary membership under Payments › Fees & Pricing. |
| G1-MAP-07 | Real tools + breadcrumbs + FTS5 (`tokenize="unicode61 remove_diacritics 2"`) scoped `under` | 2h | Every tool result has breadcrumbs. `search` handles quotes, `*`, `-` and SQL-like input safely. |
| G2-MAP-08 | Obligations Register (obligations attach to **nodes** and are inherited by new resources) + Legal Vault view | 2h | `obligations("CELEX:32022R2554 Art.30")` returns rows with status and owner. |
| G2-MAP-09 | DORA Register of Information CSV, "modeled on" the ESA template B_02 columns | 1.5h | One row per ICT contractual arrangement. Missing clauses become impact items routed to the contract's legal steward. |
| G2-MAP-10 | Metrics: `context_tokens_used`, **two** naive baselines (A = whole corpus, B = all resources in the touched L1 areas), navigation depth, fragments read / total | 1h | Both ratios are logged per run. Report both honestly: the Spec Challenger will reject a strawman baseline. |

## 5. Security constraints
- `read(uri, start, end)` resolves **only** URIs that exist in the map. No filesystem paths, no `..`, nothing outside the sandbox. A path traversal attempt returns an error.
- Connectors have no write methods. A test asserts it.
- Never index `sandbox/_ground_truth/`. Excluding it is a hard-coded rule, not a config option.

## 6. Definition of done
`make map` builds the PayRo map in under 60 seconds (excluding optional LLM polish). Map quality from `make eval`: primary path ≥ 90%, owner ≥ 90%, counterparty on ICT contracts = 100%, distractor intranet documents never tagged with DORA or IPR. The context ratio appears in `RESULTS.md`.
