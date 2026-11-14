"""The PayRo sandbox: labelled as fictional, and the seed repo starts in the designed state."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SANDBOX = Path(__file__).resolve().parents[2] / "sandbox"
SEED = SANDBOX / "repo_seed"
SOURCES = ("onedrive", "gdrive", "confluence", "jira", "intranet", "repo_seed")
FILES = [p for s in SOURCES for p in sorted((SANDBOX / s).rglob("*"))
         if p.is_file() and p.suffix in (".md", ".py", ".yaml") and p.stat().st_size and "tests" not in p.parts]


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(SANDBOX)))
def test_every_fabricated_file_is_labelled(path):
    head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:3])
    assert "FICTIONAL – PayRo SRL" in head


def _pytest(target: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", target],
                          cwd=SEED, capture_output=True, text=True, timeout=120,
                          env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})


def test_seed_repo_historical_tests_pass_and_compliance_tests_fail():
    assert _pytest("tests/historical").returncode == 0
    compliance = _pytest("tests/compliance")
    assert compliance.returncode == 1
    for name in ("test_equal_charges", "test_verification_of_payee", "test_incident_reporting"):
        assert f"FAILED tests/compliance/{name}.py" in compliance.stdout


def test_ground_truth_points_at_existing_resources():
    truth = yaml.safe_load((SANDBOX / "_ground_truth" / "expected.yaml").read_text(encoding="utf-8"))
    resources = yaml.safe_load((SANDBOX / "_ground_truth" / "resources.yaml").read_text(encoding="utf-8"))
    uris = [r["uri"] for r in resources["resources"]] + [i["uri"] for i in truth["impact_items"]]
    for uri in uris:
        source, _, rel = uri.partition("://")
        root = SEED if source == "repo" else SANDBOX / source
        assert (root / rel).is_file(), uri
    for celex in truth["laws"]["relevant"]:
        assert (SANDBOX / "feed" / f"{celex}.md").is_file()
