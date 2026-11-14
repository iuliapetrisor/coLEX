"""The PayRo repository as it is on disk: what is checked out, what coLEX proposed, and a way to run the code.

The app runs the files in the repository folder itself, so it always runs the commit that is checked out
there (normally `main`). Nothing is copied or cached: after a merge, the next request runs the merged code.
Only read-only git commands are used. The code runs in a subprocess with a scrubbed environment and no
network, like the coder's tests. File access is not sandboxed, so use this on a demo machine only.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from colex import testrunner

DRIVER = Path(__file__).with_name("driver.py")
READ_ONLY = {"rev-parse", "rev-list", "for-each-ref", "diff", "log", "status"}
SEP = "\x1f"


class PayroRepo:
    def __init__(self, repo: Path) -> None:
        self.repo = Path(repo).resolve()

    def exists(self) -> bool:
        return (self.repo / ".git").exists()

    def _git(self, *args: str) -> str:
        if args[0] not in READ_ONLY:
            raise ValueError(f"git {args[0]} is not a read-only command")
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(self.repo.parent), "LC_ALL": "C",
               "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0",
               "GIT_CEILING_DIRECTORIES": ":".join(str(p) for p in self.repo.parents)}
        done = subprocess.run(["git", *args], cwd=self.repo, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30)
        if done.returncode != 0:
            raise RuntimeError(done.stderr.strip()[:200])
        return done.stdout

    def head(self) -> dict[str, Any]:
        """What is checked out right now. This is the code every request runs."""
        line = self._git("log", "-1", f"--format=%H{SEP}%s{SEP}%cn{SEP}%cr", "HEAD").rstrip("\n")
        sha, subject, who, when = line.split(SEP)
        return {"branch": self._git("rev-parse", "--abbrev-ref", "HEAD").strip(), "sha": sha, "subject": subject,
                "who": who, "when": when,
                "uncommitted": [row[3:] for row in self._git("status", "--porcelain").splitlines()]}

    def history(self, limit: int = 6) -> list[dict[str, str]]:
        rows = self._git("log", f"-{limit}", "--first-parent", f"--format=%h{SEP}%cn{SEP}%cr{SEP}%s", "HEAD")
        return [dict(zip(("sha", "who", "when", "subject"), row.split(SEP))) for row in rows.splitlines()]

    def proposals(self) -> list[dict[str, Any]]:
        """coLEX branches that change something, newest first: merged into the checked-out code, or waiting."""
        merged_from: dict[str, str] = {}   # tip of a merged branch -> the commit it was merged into
        for row in self._git("log", "-200", "--first-parent", "--format=%H %P", "HEAD").splitlines():
            parts = row.split()
            for other in parts[2:]:
                merged_from[other] = parts[1]
        listing = self._git("for-each-ref", "--sort=-committerdate",
                            f"--format=%(refname:short){SEP}%(objectname){SEP}%(subject)", "refs/heads/colex")
        out = []
        for line in listing.splitlines():
            name, sha, subject = line.split(SEP)
            waiting = int(self._git("rev-list", "--count", f"HEAD..{sha}").strip()) > 0
            if not waiting and sha not in merged_from and not subject.startswith("colex: "):
                continue   # a branch without a change of its own
            base = "HEAD" if waiting else merged_from.get(sha, f"{sha}^")   # `sha^`: merged by fast-forward
            stat = [row.split("\t") for row in self._git("diff", "--numstat", f"{base}...{sha}").splitlines()]
            out.append({"branch": name, "sha": sha, "title": subject.removeprefix("colex: "), "merged": not waiting,
                        "files": [r[2] for r in stat],
                        "added": sum(int(r[0]) for r in stat if r[0].isdigit()),
                        "removed": sum(int(r[1]) for r in stat if r[1].isdigit())})
        return out

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        """Run the driver inside the repository folder, so `import payments` loads the files checked out there."""
        cmd = [sys.executable, "-B", str(DRIVER)]
        if testrunner.network_namespace():
            cmd = ["unshare", "-rn", *cmd]
        env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(testrunner.BLOCKER), "PYTHONDONTWRITEBYTECODE": "1",
               "LC_ALL": "C.UTF-8"}
        try:
            done = subprocess.run(cmd, cwd=self.repo, env=env, input=json.dumps(request), capture_output=True,
                                  text=True, timeout=20)
            return json.loads(done.stdout)
        except subprocess.TimeoutExpired:
            return {"error": "the code did not answer within 20 seconds"}
        except (ValueError, OSError) as exc:
            return {"error": f"the code could not be run: {type(exc).__name__}"}
