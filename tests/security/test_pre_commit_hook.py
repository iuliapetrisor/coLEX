"""The pre-commit hook blocks secrets, forbidden paths and ground-truth references."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / ".githooks" / "pre-commit"

# Built at runtime so this file never contains a token-shaped string.
FAKE_TOKEN = "xox" + "b-" + "0000000000-FAKEFAKEFAKE"
HIDDEN_DIR = "_ground" + "_truth"


def _env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=_env())


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    return tmp_path


def _stage(repo: Path, name: str, content: str) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", "-f", name)


def _run_hook(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(HOOK)], cwd=repo, capture_output=True, text=True, env=_env())


def test_hook_is_executable():
    assert os.access(HOOK, os.X_OK)


def test_clean_commit_passes(repo):
    _stage(repo, "notes.md", "nothing secret here\n")
    assert _run_hook(repo).returncode == 0


def test_token_shaped_string_is_blocked_and_not_printed(repo):
    _stage(repo, "config.py", f'TOKEN = "{FAKE_TOKEN}"\n')
    result = _run_hook(repo)
    assert result.returncode == 1
    assert "config.py" in result.stderr
    assert FAKE_TOKEN not in result.stdout + result.stderr


def test_bare_prefix_in_documentation_passes(repo):
    _stage(repo, "README.md", "Set SLACK_BOT_TOKEN to your " + "xox" + "b-" + "... token\n")
    assert _run_hook(repo).returncode == 0


@pytest.mark.parametrize("name", [".env", "sub/.env", ".env.local", "colex.db", "var/run.txt", "data/map.sqlite"])
def test_forbidden_paths_are_blocked(repo, name):
    _stage(repo, name, "x\n")
    result = _run_hook(repo)
    assert result.returncode == 1
    assert name in result.stderr


def test_env_example_passes(repo):
    _stage(repo, ".env.example", "OPENROUTER_API_KEY=\n")
    assert _run_hook(repo).returncode == 0


def test_ground_truth_reference_in_runtime_code_is_blocked(repo):
    _stage(repo, "colex/agents/impact.py", f'PATH = "sandbox/{HIDDEN_DIR}/expected.yaml"\n')
    result = _run_hook(repo)
    assert result.returncode == 1
    assert "colex/agents/impact.py" in result.stderr


def test_ground_truth_reference_in_tests_passes(repo):
    _stage(repo, "tests/eval/test_eval.py", f'PATH = "sandbox/{HIDDEN_DIR}/expected.yaml"\n')
    assert _run_hook(repo).returncode == 0
