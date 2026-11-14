"""Personal data is replaced before it reaches a model or storage."""
from __future__ import annotations

from colex.guardrails.redaction import RedactionCtx, _WEIGHTS, mask, redact, unredact


def _cnp(first12: str) -> str:
    check = sum(int(d) * w for d, w in zip(first12, _WEIGHTS)) % 11
    return first12 + str(1 if check == 10 else check)


CNP = _cnp("385010112345")  # sex digit 3: born in the 1800s, cannot belong to a living person
TEXT = f"Client CNP {CNP}, IBAN RO49 AAAA 1B31 0075 9384 0000, mail ana.pop@payro.example, tel 0722 123 456."


def test_redact_replaces_every_category_and_is_reversible():
    ctx = RedactionCtx()
    out = redact(TEXT, ctx)
    for secret in (CNP, "RO49 AAAA", "ana.pop@payro.example", "0722 123 456"):
        assert secret not in out
    assert out.count("⟨") == 4
    assert unredact(out, ctx) == TEXT


def test_same_value_gets_the_same_placeholder():
    ctx = RedactionCtx()
    assert redact("a@payro.example and a@payro.example", ctx).split(" and ")[0] == redact("a@payro.example", ctx)


def test_numbers_that_are_not_valid_cnps_are_kept():
    not_cnp = CNP[:12] + str((int(CNP[12]) + 1) % 10)
    assert not_cnp in redact(f"order {not_cnp}", RedactionCtx())
    assert "1234567890" in mask("ticket 1234567890")


def test_mask_is_one_way_and_also_hides_tokens():
    out = mask(TEXT + " key sk-o" + "r-v1-abcdefabcdef")
    assert CNP not in out and "payro.example" not in out and "abcdefabcdef" not in out
    assert "⟨IBAN⟩" in out and "⟨EMAIL⟩" in out
