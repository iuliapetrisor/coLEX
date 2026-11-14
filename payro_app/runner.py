"""Read-only access to the sandbox repository: list versions, export one commit, run its code.

Only read-only git subcommands are used. The code of a version runs in a subprocess with a scrubbed
environment and no network, like the coder's tests. It is model-written code when the version is a
coLEX branch: file access is not sandboxed, so run this on a demo machine only.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

from colex import testrunner

DRIVER = Path(__file__).with_name("driver.py")
READ_ONLY = {"rev-parse", "rev-list", "for-each-ref", "archive", "diff"}


class PayroRepo:
    def __init__(self, repo: Path, cache: Path) -> None:
        self.repo, self.cache = Path(repo).resolve(), Path(cache).resolve()

    def exists(self) -> bool:
        return (self.repo / ".git").exists()

    def _git(self, *args: str) -> bytes:
        if args[0] not in READ_ONLY:
            raise ValueError(f"git {args[0]} is not a read-only command")
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(self.repo.parent), "LC_ALL": "C",
               "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
               "GIT_CEILING_DIRECTORIES": ":".join(str(p) for p in self.repo.parents)}
        done = subprocess.run(["git", *args], cwd=self.repo, env=env, capture_output=True, timeout=30)
        if done.returncode != 0:
            raise RuntimeError(done.stderr.decode("utf-8", "replace").strip()[:200])
        return done.stdout

    def versions(self) -> list[dict[str, Any]]:
        """'original' (the first commit), 'main', then every coLEX branch, newest first."""
        seed = self._git("rev-list", "--max-parents=0", "main").decode().split()[0]
        out = [{"ref": "original", "sha": seed, "title": "the code before any change", "files": [], "merged": True},
               {"ref": "main", "sha": self._git("rev-parse", "main").decode().strip(),
                "title": "what customers get today", "files": [], "merged": True}]
        listing = self._git("for-each-ref", "--sort=-committerdate",
                            "--format=%(refname:short)%09%(objectname)%09%(subject)", "refs/heads/colex").decode()
        for line in listing.splitlines():
            name, sha, subject = (line.split("\t") + ["", ""])[:3]
            ahead = int(self._git("rev-list", "--count", f"main..{sha}").decode().strip())
            files = self._git("diff", "--name-only", f"{seed}...{sha}").decode().split()
            if files:   # a branch with no change of its own has nothing to show
                out.append({"ref": name, "sha": sha, "title": subject.removeprefix("colex: "), "files": files,
                            "merged": ahead == 0})
        return out

    def export(self, sha: str) -> Path:
        """A copy of the `payments` package at one commit, cached by commit id."""
        target = self.cache / sha
        if not target.is_dir():
            tmp = self.cache / f"{sha}.tmp{os.getpid()}"
            shutil.rmtree(tmp, ignore_errors=True)
            tmp.mkdir(parents=True)
            with tarfile.open(fileobj=io.BytesIO(self._git("archive", "--format=tar", sha, "payments"))) as tar:
                tar.extractall(tmp, filter="data")
            try:
                tmp.rename(target)
            except OSError:   # another request exported the same commit first
                shutil.rmtree(tmp, ignore_errors=True)
        return target

    def run(self, ref: str, request: dict[str, Any]) -> dict[str, Any]:
        """Run the driver inside the code of `ref`. `ref` must be one of versions()."""
        version = next((v for v in self.versions() if v["ref"] == ref), None)
        if version is None:
            return {"ref": ref, "sha": "", "error": "unknown version"}
        cmd = [sys.executable, "-B", str(DRIVER)]
        if testrunner.network_namespace():
            cmd = ["unshare", "-rn", *cmd]
        env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(testrunner.BLOCKER), "PYTHONDONTWRITEBYTECODE": "1",
               "LC_ALL": "C.UTF-8"}
        try:
            done = subprocess.run(cmd, cwd=self.export(version["sha"]), env=env, input=json.dumps(request),
                                  capture_output=True, text=True, timeout=20)
            result = json.loads(done.stdout)
        except subprocess.TimeoutExpired:
            result = {"error": "this version did not answer within 20 seconds"}
        except (ValueError, RuntimeError, OSError) as exc:
            result = {"error": f"this version could not be run: {type(exc).__name__}"}
        return {"ref": ref, "sha": version["sha"], **result}
