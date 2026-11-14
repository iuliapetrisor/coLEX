"""One valid payload per model named in brief §4.2. All company data here is fictional (PayRo)."""
from __future__ import annotations

TS = "2026-11-14T10:00:00Z"
LINES = {"start": 12, "end": 12}
ITEM = {
    "item_id": "item-1",
    "article_id": "Art. 5",
    "resource_uri": "repo://payments/fees.yaml",
    "lines": LINES,
    "action": "CONFIG_CHANGE",
    "owner_team": "product",
    "evidence": "instant_eur: 1.50",
    "citation": "CELEX:32024R0886 Art. 5",
    "confidence": 0.9,
    "deadline": "2027-01-09",
}
QUESTION = {
    "to_team": "legal",
    "text": "Does this cover RON transfers?",
    "options": ["yes", "no"],
    "blocking_items": ["item-1"],
}
SUITE = {"passed": 10, "failed": 2, "failing_tests": ["tests/compliance/test_vop.py::test_vop"]}

VALID = {
    "TaxonomyNode": {"node_id": "n-1", "parent_id": None, "level": "L1", "name": "Payments",
                     "path": "PayRo › Payments"},
    "ResourceCard": {"uri": "repo://payments/fees.yaml", "source": "repo", "info_type": "config",
                     "primary_path": "PayRo › Technology & Security › Configuration",
                     "ownership_source": "explicit", "owner_team": "payments-eng",
                     "regulatory_tags": [{"citation": "CELEX:32024R0886 Art. 5", "status": "gap"}],
                     "classification_confidence": 0.8, "sha": "abc123", "map_version_id": "mv-1"},
    "Counterparty": {"counterparty_id": "cp-aws", "canonical_name": "Amazon Web Services EMEA SARL",
                     "aliases": ["AWS"], "type": "ict_provider"},
    "Fragment": {"uri": "repo://payments/transfer.py", "title": "authorize_transfer", "kind": "function",
                 "lines": {"start": 40, "end": 71}},
    "Entity": {"uri": "repo://payments/fees.yaml", "etype": "fee", "value": "1.50", "line": 12},
    "Edge": {"src": "repo://payments/fees.yaml", "dst": "gdrive://product/fee-schedule.md",
             "kind": "implements", "evidence": {"uri": "repo://payments/fees.yaml", "lines": LINES}},
    "LawDocument": {"celex": "32024R0886", "title": "Instant Payments Regulation",
                    "source": "https://eur-lex.europa.eu/", "published": "2024-03-19",
                    "articles": [{"id": "Art. 5", "text": "placeholder, not legal text",
                                  "effective_dates": ["2027-01-09"]}]},
    "LawArticle": {"id": "Art. 5", "text": "placeholder, not legal text"},
    "TriageResult": {"law_id": "32024R0886", "relevant": True, "articles_flagged": ["Art. 5"],
                     "reason": "PayRo sends euro credit transfers", "confidence": 0.95},
    "ImpactItem": ITEM,
    "Question": QUESTION,
    "Notification": {"channel": "#product", "title": "IPR equal charges", "body": "1 item",
                     "items": [ITEM], "actions": ["acknowledge", "assign", "dispute"]},
    "ChangeRequest": {"branch": "colex/run-1/item-1", "diff": "", "tests_before": SUITE,
                      "iterations": 0, "status": "draft"},
    "AuditEvent": {"ts": TS, "agent": "triage", "step": "TRIAGE", "tokens_in": 100, "tokens_out": 20,
                   "cost_usd": 0.001, "duration_ms": 800},
    "Run": {"run_id": "run-1", "law_id": "32024R0886", "status": "running", "current_node": "TRIAGE",
            "branches": {"item-1": "waiting_for_legal"}, "config_version_id": "cv-1"},
    "Checkpoint": {"checkpoint_id": "cp-1", "run_id": "run-1", "branch_id": "main", "node": "TRIAGE",
                   "state_ref": "blob-1", "pending_questions": [QUESTION], "config_version_id": "cv-1",
                   "ts": TS},
    "ConfigVersion": {"version_id": "cv-1", "hash": "h", "author": "alexia", "ts": TS,
                      "payload": {"budgets": {"max_iterations": 3}}},
}
