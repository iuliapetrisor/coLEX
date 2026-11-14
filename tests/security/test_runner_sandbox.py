"""The sandboxed test runner contains hanging tests, network use and attempts to read secrets."""
from __future__ import annotations

import pytest

from colex import testrunner


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "wt"
    (root / "tests").mkdir(parents=True)
    (root / "conftest.py").write_text("", encoding="utf-8")
    return root


def _write(repo, body: str) -> None:
    (repo / "tests" / "test_case.py").write_text(body, encoding="utf-8")


def test_results_come_from_junit_with_names_and_messages(repo):
    _write(repo, "import pytest\n\ndef test_ok():\n    assert True\n\ndef test_bad():\n    assert 1 == 2\n\n"
                 "@pytest.mark.parametrize('n', [1, 2])\ndef test_p(n):\n    assert n == 1\n")
    out = testrunner.run_tests(repo, timeout=30)
    assert out["passed"] == ["tests/test_case.py::test_ok", "tests/test_case.py::test_p[1]"]
    assert out["failed"] == ["tests/test_case.py::test_bad", "tests/test_case.py::test_p[2]"]
    assert "1 == 2" in out["details"]["tests/test_case.py::test_bad"]
    assert out["ok"] is False and out["unusable"] is False
    assert testrunner.suite(out) == {"passed": 2, "failed": 2, "errors": 0, "failing_tests": out["failed"]}


def test_hanging_test_is_killed_with_its_children(repo):
    _write(repo, "import subprocess, time\n\ndef test_hang():\n    subprocess.Popen(['sleep', '300'])\n"
                 "    time.sleep(300)\n")
    out = testrunner.run_tests(repo, timeout=3)
    assert out["timed_out"] is True and out["unusable"] is True and out["ok"] is False


def test_network_is_blocked(repo):
    _write(repo, "import socket, urllib.request\n\ndef test_socket():\n    s = socket.socket()\n"
                 "    s.connect(('1.1.1.1', 80))\n\ndef test_http():\n"
                 "    urllib.request.urlopen('http://example.com', timeout=3)\n")
    out = testrunner.run_tests(repo, timeout=30)
    assert len(out["failed"]) == 2 and out["passed"] == []


def test_secrets_of_the_parent_process_are_not_visible(repo, monkeypatch):
    for name in ("OPENROUTER_API_KEY", "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "HTTPS_PROXY"):
        monkeypatch.setenv(name, "value-that-must-not-leak")
    _write(repo, "import os\n\ndef test_env():\n    leaked = [k for k in os.environ if 'KEY' in k or 'TOKEN' in k "
                 "or 'PROXY' in k.upper()]\n    assert leaked == []\n"
                 "    assert 'value-that-must-not-leak' not in ' '.join(os.environ.values())\n")
    assert testrunner.run_tests(repo, timeout=30)["ok"] is True


def test_a_parent_pytest_ini_is_ignored(repo):
    """Regression: a worktree under a project with its own pytest.ini (as under coLEX's var/) used that
    project as root, so test ids did not match files and the parent's code was importable."""
    (repo.parent / "pytest.ini").write_text("[pytest]\npythonpath = .\ntestpaths = nowhere\n", encoding="utf-8")
    (repo.parent / "outer_secret_module.py").write_text("VALUE = 1\n", encoding="utf-8")
    _write(repo, "import importlib.util\n\ndef test_ok():\n"
                 "    assert importlib.util.find_spec('outer_secret_module') is None\n")
    out = testrunner.run_tests(repo, timeout=30)
    assert out["passed"] == ["tests/test_case.py::test_ok"] and out["ok"] is True


def test_a_suite_that_collects_nothing_is_unusable_not_green(repo):
    _write(repo, "def helper():\n    return 1\n")
    out = testrunner.run_tests(repo, timeout=30)
    assert out["ok"] is False and out["unusable"] is True
