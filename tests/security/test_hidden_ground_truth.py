"""Runtime code, prompts and config never reference the hidden evaluation data (README §2 rule 9)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HIDDEN = "_ground" + "_truth"   # built at runtime so this file does not trip its own check


def test_runtime_code_prompts_and_config_never_mention_the_hidden_data():
    offenders = [str(p.relative_to(ROOT)) for folder in ("colex", "prompts", "config")
                 for p in (ROOT / folder).rglob("*") if p.is_file() and p.suffix in (".py", ".md", ".yaml")
                 and HIDDEN in p.read_text(encoding="utf-8")]
    assert offenders == []
