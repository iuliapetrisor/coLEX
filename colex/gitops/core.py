"""Git access for agents: a subcommand allowlist and the merge-lock hook.

There is no way to run merge, push, checkout, reset, rebase or update-ref from here. As a second
lock, the sandbox repository has a `reference-transaction` hook that rejects every update of
`refs/heads/main` while COLEX_AGENT=1, which agent calls always set.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ALLOWED = {
    "init": None, "add": None, "commit": None, "diff": None, "rev-parse": None, "status": None,
    "log": None, "ls-files": None,
    "worktree": {"add", "remove", "prune", "list"},
    "config": {"user.name", "user.email", "commit.gpgsign"},
}
HOOK = """#!/bin/sh
# coLEX merge lock: while an agent is acting (COLEX_AGENT=1), refs/heads/main cannot change.
[ "$COLEX_AGENT" = "1" ] || exit 0
[ "$1" = "prepared" ] || exit 0
while read old new ref; do
  if [ "$ref" = "refs/heads/main" ]; then
    echo "coLEX merge lock: agents cannot update refs/heads/main" >&2
    exit 1
  fi
done
exit 0
"""


class ForbiddenGitOperation(RuntimeError):
    pass


class GitError(RuntimeError):
    pass


class GitCore:
    def __init__(self, repo: Path, worktrees: Path) -> None:
        self.repo, self.worktrees = Path(repo).resolve(), Path(worktrees).resolve()

    def _git(self, *args: str, cwd: Path | None = None, agent: bool = True) -> str:
        sub = args[0] if args else ""
        if sub not in ALLOWED or (ALLOWED[sub] is not None and (len(args) < 2 or args[1] not in ALLOWED[sub])):
            raise ForbiddenGitOperation(f"git {' '.join(args[:2])} is not allowed for agents")
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(self.repo.parent),
               "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C",
               "GIT_CEILING_DIRECTORIES": str(self.repo.parent)}
        if agent:
            env["COLEX_AGENT"] = "1"
        done = subprocess.run(["git", *args], cwd=cwd or self.repo, env=env, capture_output=True, text=True,
                              timeout=60)
        if done.returncode != 0:
            raise GitError(f"git {sub} failed: {(done.stderr or done.stdout).strip()[:300]}")
        return done.stdout

    def seed(self, source: Path) -> str:
        """Create the sandbox repository from the seed folder, if it does not exist. Returns the base sha.

        Run by `make demo` or the server at start-up, not by an agent: it creates main's first commit.
        """
        if not (self.repo / ".git").is_dir():
            shutil.copytree(source, self.repo, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
            self._git("init", "-q", "-b", "main", agent=False)
            for key, value in (("user.name", "coLEX agent"), ("user.email", "colex-agent@payro.example"),
                               ("commit.gpgsign", "false")):
                self._git("config", key, value, agent=False)
            self._git("add", "-A", agent=False)
            self._git("commit", "-q", "-m", "seed: PayRo payments repository (fictional)", agent=False)
            hook = self.repo / ".git" / "hooks" / "reference-transaction"
            hook.write_text(HOOK, encoding="utf-8")
            hook.chmod(0o755)
        return self.base()

    def base(self) -> str:
        return self._git("rev-parse", "main").strip()
