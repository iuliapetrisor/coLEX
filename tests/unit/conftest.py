"""Fixtures shared by the unit tests."""
from __future__ import annotations

import pytest


@pytest.fixture
def tools(colex_db_path):
    """Map tools on a freshly built PayRo map."""
    from colex.config import ConfigStore
    from colex.map import build as build_mod
    from colex.map.tools import MapTools

    cfg = ConfigStore().active().payload
    build_mod.build(cfg)
    return MapTools(cfg)
