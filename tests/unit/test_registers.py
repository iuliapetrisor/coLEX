"""DORA Register of Information and Obligations Register, generated from the map."""
from __future__ import annotations

import csv
import io

from colex.map import registers

ICT = "PayRo › Legal & Compliance › Contracts › ICT provider contracts"


def _by_provider(tools):
    return {r["provider_id"]: r for r in registers.dora_rows(tools.mv)}


def test_one_row_per_ict_contract_with_criticality_location_and_gaps(tools):
    rows = _by_provider(tools)
    assert len(rows) == 6
    aws = rows["cp-aws"]
    assert (aws["provider"], aws["supports_critical_or_important_function"], aws["data_processing_locations"]) == \
           ("Amazon Web Services EMEA SARL", "yes", "Germany, Ireland")
    assert aws["missing_clauses_art_30_2"] == aws["missing_clauses_art_30_3"] == ""
    assert rows["cp-smsnord"]["missing_clauses_art_30_3"] == "30(3)(e)"
    assert rows["cp-smsnord"]["subcontractors"] == "Baltic Carrier Hub OÜ"
    assert rows["cp-ledgercore"]["missing_clauses_art_30_3"] == "30(3)(f)"
    kyc = rows["cp-verifid"]
    assert (kyc["missing_clauses_art_30_2"], kyc["data_processing_locations"], kyc["owner_team"]) == \
           ("30(2)(b)", "not specified", "unknown")


def test_30_3_clauses_are_not_flagged_for_non_critical_contracts(tools):
    rows = _by_provider(tools)
    for provider in ("cp-verifid", "cp-namematch"):          # not critical: only 30(2) applies
        assert rows[provider]["supports_critical_or_important_function"] == "no"
        assert rows[provider]["missing_clauses_art_30_3"] == "" and rows[provider]["to_check_if_critical"] == ""
    card = rows["cp-cardaxis"]                                # not assessed: listed to check, not as a gap
    assert card["supports_critical_or_important_function"] == "not assessed"
    assert card["missing_clauses_art_30_3"] == "" and "30(3)(e)" in card["to_check_if_critical"]


def test_csv_has_the_documented_columns(tools):
    parsed = list(csv.DictReader(io.StringIO(registers.dora_csv(tools.mv))))
    assert list(parsed[0]) == registers.COLUMNS and len(parsed) == 6
    assert not [k for k in parsed[0] if k.startswith("_")]


def test_obligations_attach_to_nodes_and_are_not_duplicated(tools):
    item = {"item_id": "i1", "citation": "CELEX:32022R2554 Art. 30", "obligation": "Add audit rights.",
            "breadcrumbs": ICT, "resource_uri": "onedrive://legal/contracts/sms-otp-smsnord.md",
            "lines": {"start": 7, "end": 7}, "owner_team": "legal", "deadline": None, "action": "CONTRACT_REVIEW"}
    for _ in range(2):
        assert registers.record_obligations("run-1", "32022R2554", [item]) == 1
    assert len(registers.obligation_rows()) == 1
    by_article = tools.obligations("CELEX:32022R2554 Art.30")
    assert by_article["total"] == 1 and by_article["items"][0]["status"] == "gap"
    assert tools.obligations(path="PayRo › Legal & Compliance")["total"] == 1      # ancestor node
    assert tools.obligations(path="PayRo › Payments")["total"] == 0


def test_legal_vault_is_a_view_over_legal_resources(tools):
    vault = registers.legal_vault(tools.mv)
    types = {v["info_type"] for v in vault}
    assert types == {"contract", "customer_terms", "fee_schedule", "policy", "procedure"}
    assert not [v for v in vault if v["uri"].startswith("repo://")]
