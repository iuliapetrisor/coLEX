"""FICTIONAL – PayRo SRL is a fabricated company for the coLEX demo.

Reads customer fees from fees.yaml.
"""
from __future__ import annotations

from pathlib import Path

import yaml

FEES_FILE = Path(__file__).with_name("fees.yaml")


def load_fees() -> dict:
    return yaml.safe_load(FEES_FILE.read_text(encoding="utf-8"))["fees"]


def fee_for(currency: str, instant: bool) -> float:
    return float(load_fees()[currency.lower()]["instant" if instant else "standard"])
