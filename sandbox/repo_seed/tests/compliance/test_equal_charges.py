"""FICTIONAL – PayRo SRL demo. Compliance test.

Regulation (EU) 2024/886, Article 5b(1) inserted into Regulation (EU) No 260/2012: charges for instant
credit transfers shall not be higher than charges for other credit transfers of corresponding type.
"""
from payments.fees import fee_for


def test_instant_euro_transfer_costs_no_more_than_a_standard_one():
    assert fee_for("EUR", instant=True) <= fee_for("EUR", instant=False)
