"""Sandboxed test runner for the coder (brief §4.3).

pytest in a subprocess: working directory locked to the worktree, a scrubbed environment (no API
keys, no Slack tokens, no proxy variables), no network (socket block in the child, plus a network
namespace when `unshare` works on this host), CPU and memory limits, and a timeout that kills the
whole process group. Results come from the JUnit XML file, never from parsing console text.
"""
from __future__ import annotations

import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import Any

BLOCKER = Path(__file__).parent / "blocker"
MEMORY_BYTES = 4 * 1024 ** 3


@lru_cache(maxsize=1)
def network_namespace() -> bool:
    """True when this host lets an unprivileged process create a network namespace."""
    if not shutil.which("unshare"):
        return False
    try:
        return subprocess.run(["unshare", "-rn", "true"], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _limits(seconds: int):
    def apply() -> None:
        os.setsid()
        resource.setrlimit(resource.RLIMIT_CPU, (seconds + 5, seconds + 5))
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
    return apply


def _parse(xml_path: Path) -> dict[str, Any]:
    passed, failed, errors, details = [], [], [], {}
    for case in ET.parse(xml_path).getroot().iter("testcase"):
        test_id = f"{case.get('classname', '').replace('.', '/')}.py::{case.get('name', '')}"
        problem = case.find("failure")
        broken = case.find("error")
        if problem is not None or broken is not None:
            node = problem if problem is not None else broken
            (failed if problem is not None else errors).append(test_id)
            details[test_id] = ((node.get("message") or "") + "\n" + (node.text or "")).strip()
        elif case.find("skipped") is None:
            passed.append(test_id)
    return {"passed": sorted(passed), "failed": sorted(failed), "errors": sorted(errors), "details": details}


def run_tests(worktree: Path, timeout: int = 60) -> dict[str, Any]:
    """Run the whole test suite of a worktree. Never raises for a failing or hanging suite."""
    worktree = Path(worktree).resolve()
    with tempfile.TemporaryDirectory(prefix="colex-tests-", dir=worktree.parent) as tmp:
        xml_path = Path(tmp) / "junit.xml"
        env = {"PATH": "/usr/bin:/bin", "HOME": tmp, "TMPDIR": tmp, "PYTHONPATH": str(BLOCKER),
               "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "LC_ALL": "C.UTF-8"}
        ini = Path(tmp) / "pytest.ini"   # an empty config of our own: parent directories are never consulted
        ini.write_text("[pytest]\n", encoding="utf-8")
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=short",
               "-c", str(ini), f"--rootdir={worktree}",
               f"--junitxml={xml_path}", "-o", "junit_family=xunit1"]
        if network_namespace():
            cmd = ["unshare", "-rn", *cmd]
        proc = subprocess.Popen(cmd, cwd=worktree, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, preexec_fn=_limits(timeout))
        try:
            output, _ = proc.communicate(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            output, _ = proc.communicate()
            timed_out = True
        result = {"passed": [], "failed": [], "errors": [], "details": {}}
        if xml_path.is_file() and not timed_out:
            try:
                result = _parse(xml_path)
            except ET.ParseError:
                pass
    collected = bool(result["passed"] or result["failed"] or result["errors"])
    result.update(timed_out=timed_out, exit_code=proc.returncode, output_tail=output[-2500:],
                  ok=not timed_out and collected and not result["failed"] and not result["errors"],
                  unusable=timed_out or not collected, network_namespace=network_namespace())
    return result


def suite(result: dict[str, Any]) -> dict[str, Any]:
    """SuiteResult fields (brief §4.2) from a runner result."""
    bad = result["failed"] + result["errors"]
    return {"passed": len(result["passed"]), "failed": len(result["failed"]), "errors": len(result["errors"]),
            "failing_tests": sorted(bad)}
