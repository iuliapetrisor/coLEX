"""GitOps: the only way the coder touches git (brief §4.3). Merging is a manual human step."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from colex.gitops.core import ForbiddenGitOperation, GitCore, GitError  # noqa: F401

SAFE = re.compile(r"[^A-Za-z0-9._-]+")


class GitOps(GitCore):
    def branch_name(self, run_id: str, item_id: str) -> str:
        return f"colex/{SAFE.sub('-', run_id)}/{SAFE.sub('-', item_id)}"

    def _path(self, run_id: str, item_id: str) -> Path:
        return self.worktrees / SAFE.sub("-", run_id) / SAFE.sub("-", item_id)

    def _has(self, branch: str) -> bool:
        try:
            self._git("rev-parse", "--verify", "-q", f"refs/heads/{branch}")
            return True
        except GitError:
            return False

    def create_branch(self, run_id: str, item_id: str) -> tuple[str, Path]:
        """Branch 'colex/<run>/<item>' from main in its own worktree. An existing branch is reused.

        A worktree left dirty by a crashed run is discarded and recreated at the branch tip.
        """
        name, path = self.branch_name(run_id, item_id), self._path(run_id, item_id)
        exists = self._has(name)
        if path.is_dir() and exists and not self._git("status", "--porcelain", cwd=path).strip():
            return name, path
        if path.is_dir():
            try:
                self._git("worktree", "remove", "--force", str(path))
            except GitError:
                shutil.rmtree(path, ignore_errors=True)
        self._git("worktree", "prune")
        path.parent.mkdir(parents=True, exist_ok=True)
        if exists:
            self._git("worktree", "add", "-q", str(path), name)
        else:
            self._git("worktree", "add", "-q", "-b", name, str(path), "main")
        return name, path

    def changed(self, worktree: Path) -> list[str]:
        """Paths that differ from the branch tip in the worktree (modified, added or deleted)."""
        out = self._git("status", "--porcelain", "--untracked-files=all", cwd=worktree)
        return sorted(line[3:].strip().strip('"') for line in out.splitlines() if line.strip())

    def commit(self, worktree: Path, message: str, idempotency_key: str) -> str:
        """Commit everything in the worktree. The same key never creates a second commit."""
        trailer = f"Colex-Key: {idempotency_key}"
        log = self._git("log", "--format=%H%x00%B%x01", "main..HEAD", cwd=worktree)
        for entry in log.split("\x01"):
            if trailer in entry:
                return entry.split("\x00")[0].strip()
        self._git("add", "-A", cwd=worktree)
        self._git("commit", "-q", "-m", f"{message}\n\n{trailer}", cwd=worktree)
        return self._git("rev-parse", "HEAD", cwd=worktree).strip()

    def diff(self, branch: str) -> str:
        return self._git("diff", f"main...{branch}")

    def head(self, worktree: Path) -> str:
        return self._git("rev-parse", "HEAD", cwd=worktree).strip()
