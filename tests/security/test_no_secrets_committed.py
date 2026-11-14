"""No secret may be tracked by git, and .env must stay ignored (brief §4.3)."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# A known token prefix followed by a token body. Bare prefixes in documentation do not match.
TOKEN = re.compile(rb"(xox[a-z]|xapp|sk-or)-[A-Za-z0-9_-]{10,}")


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True)


@pytest.fixture(scope="module")
def tracked_files() -> list[Path]:
    result = _git("ls-files", "-z")
    if result.returncode != 0:
        pytest.skip("not a git checkout")
    return [REPO / name.decode() for name in result.stdout.split(b"\0") if name]


def test_no_token_shaped_string_in_tracked_files(tracked_files):
    offenders = [
        str(path.relative_to(REPO))
        for path in tracked_files
        if path.is_file() and TOKEN.search(path.read_bytes())
    ]
    assert offenders == []


def test_env_file_is_not_tracked(tracked_files):
    names = {path.name for path in tracked_files}
    assert ".env" not in names


def test_env_file_is_ignored(tracked_files):
    assert _git("check-ignore", "-q", ".env").returncode == 0


def test_env_example_is_not_ignored(tracked_files):
    assert _git("check-ignore", "-q", ".env.example").returncode == 1


def test_env_example_holds_no_values():
    for line in (REPO / ".env.example").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            name, _, value = line.partition("=")
            assert value == "", f"{name} must be empty in .env.example"
