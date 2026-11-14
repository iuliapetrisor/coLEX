"""JSON schemas of the tools the Impact Analyst may call. `unclassified` is deliberately absent."""
from __future__ import annotations

from typing import Any

RATIONALE = {"type": "string", "description": "One line: why this call follows from the article or the "
                                              "previous result."}
PATH = {"type": "string", "description": "Map path, e.g. 'PayRo › Payments › Transfers'."}
FACETS = {"type": "object", "description": "Optional filters: info_type, owner_team, source, counterparty, "
                                           "critical (true/false/unknown), ownership_source, has_gaps (true/false)."}
ACTIONS = ["CONTRACT_REVIEW", "TERMS_UPDATE", "FEE_CHANGE", "POLICY_UPDATE", "CODE_CHANGE", "CONFIG_CHANGE"]


def _tool(name: str, description: str, props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": {**props, "rationale": RATIONALE}, "required": [*required, "rationale"]}}}


MAP_TOOLS = [
    _tool("overview", "Company profile and the business areas (L1) with their rollup summaries. Call first.", {}, []),
    _tool("browse", "Child nodes of a map path with rollup summaries (counts, gaps, owners, contractors).",
          {"path": PATH, "depth": {"type": "integer", "enum": [1, 2]}, "facets": FACETS}, ["path"]),
    _tool("list_resources", "Resource cards under a map path (no content).",
          {"path": PATH, "facets": FACETS, "cursor": {"type": "integer"}}, ["path"]),
    _tool("find", "Where an entity occurs, with uri and line. etype: fee, deadline, payment_flow, ict_provider, "
                  "contract_clause, legal_ref, personal_data, currency, jurisdiction, code_symbol.",
          {"etype": {"type": "string"}, "value": {"type": "string", "description": "Optional substring of the value."},
           "under": PATH, "cursor": {"type": "integer"}}, ["etype"]),
    _tool("search", "Full-text search over fragments (sections, functions, config keys), optionally under a path.",
          {"text": {"type": "string"}, "under": PATH, "cursor": {"type": "integer"}}, ["text"]),
    _tool("counterparty", "Everything about one contractor: contract, criticality, data location, code, tickets.",
          {"name": {"type": "string"}}, ["name"]),
    _tool("owners", "Resources a team owns, grouped by path. Use 'unknown' for resources with no owner.",
          {"team": {"type": "string"}}, ["team"]),
    _tool("related", "Cross-links of a resource or path, with evidence. kinds: governed_by, implements, "
                     "same_counterparty, references, depends_on, same_owner.",
          {"uri_or_path": {"type": "string"}, "kinds": {"type": "array", "items": {"type": "string"}}},
          ["uri_or_path"]),
    _tool("obligations", "Obligations Register rows for a law article or a map path.",
          {"article": {"type": "string"}, "path": PATH}, []),
    _tool("read", "Lines start..end of a resource that an earlier result returned. At most 40 lines per call; read narrowly.",
          {"uri": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, ["uri", "start", "end"]),
]

REPORT_TOOLS = [
    {"type": "function", "function": {"name": "report_impact", "description":
        "Report one place that must change. Checked against the law text and the lines you read.",
        "parameters": {"type": "object", "properties": {
            "article_id": {"type": "string"}, "resource_uri": {"type": "string"},
            "start": {"type": "integer"}, "end": {"type": "integer"},
            "quote": {"type": "string", "description": "Exact text from the cited lines."},
            "action": {"type": "string", "enum": ACTIONS}, "obligation": {"type": "string"},
            "deadline": {"type": "string", "description": "YYYY-MM-DD, only if written in the cited article."},
            "confidence": {"type": "number"}},
            "required": ["article_id", "resource_uri", "start", "end", "quote", "action", "obligation", "confidence"]}}},
    {"type": "function", "function": {"name": "ask_legal", "description":
        "Ask the legal team instead of guessing, when a needed fact is unknown or the article is ambiguous.",
        "parameters": {"type": "object", "properties": {
            "question": {"type": "string"}, "options": {"type": "array", "items": {"type": "string"}},
            "article_id": {"type": "string"}, "resource_uri": {"type": "string"},
            "start": {"type": "integer"}, "end": {"type": "integer"},
            "blocking_item_ids": {"type": "array", "items": {"type": "string"},
                                  "description": "Ids of reported items that depend on the answer."}},
            "required": ["question", "options", "article_id"]}}},
    {"type": "function", "function": {"name": "finish", "description": "No unexplored candidate remains.",
        "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}}},
]

MAP_TOOL_NAMES = {t["function"]["name"] for t in MAP_TOOLS}
