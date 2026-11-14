"""No code path lets an agent merge or move main (brief §4.3, §9). Two locks: the class, and a git hook."""
from __future__ import annotations

import os
import subprocess

import pytest

from colex import settings
from colex.gitops import ForbiddenGitOperation, GitError, GitOps


@pytest.fixture
def git(tmp_path):
    ops = GitOps(tmp_path / "repo", tmp_path / "worktrees")
    ops.seed(settings.SANDBOX / "repo_seed")
    return ops


def _raw(git, *args, agent: bool):
    env = {"PATH": os.environ["PATH"], "HOME": str(git.repo.parent), "GIT_CONFIG_NOSYSTEM": "1"}
    if agent:
        env["COLEX_AGENT"] = "1"
    return subprocess.run(["git", *args], cwd=git.repo, env=env, capture_output=True, text=True)


def _branch_with_commit(git):
    name, path = git.create_branch("run-1", "i1")
    (path / "payments" / "fees.yaml").write_text("fees: {}\n", encoding="utf-8")
    git.commit(path, "change fees", "pr:run-1:i1")
    return name, path


def test_class_has_no_merge_or_push_and_refuses_other_subcommands(git):
    for name in ("merge", "push", "checkout", "reset", "rebase", "pull", "fetch", "cherry_pick", "update_ref"):
        assert not hasattr(GitOps, name)
    for args in (("merge", "x"), ("push", "origin", "main"), ("checkout", "main"), ("reset", "--hard"),
                 ("rebase", "main"), ("update-ref", "refs/heads/main", "HEAD"), ("branch", "-f", "main"),
                 ("worktree", "move", "a", "b"), ("config", "core.hooksPath", "/dev/null"), ("-c", "x=y", "merge")):
        with pytest.raises(ForbiddenGitOperation):
            git._git(*args)


def test_hook_rejects_every_way_of_moving_main_while_an_agent_acts(git):
    name, path = _branch_with_commit(git)
    base = git.base()
    for args in (("merge", name), ("update-ref", "refs/heads/main", name), ("branch", "-f", "main", name),
                 ("reset", "--hard", name), ("commit", "--allow-empty", "-m", "x")):
        done = _raw(git, *args, agent=True)
        assert done.returncode != 0, args
        assert git.base() == base, args
    assert "merge lock" in _raw(git, "merge", name, agent=True).stderr


def test_a_human_can_still_merge_manually(git):
    name, _ = _branch_with_commit(git)
    assert _raw(git, "merge", "-q", name, agent=False).returncode == 0
    assert "fees: {}" in (git.repo / "payments" / "fees.yaml").read_text(encoding="utf-8")


def test_commit_is_idempotent_and_branch_is_reused(git):
    name, path = _branch_with_commit(git)
    first = git._git("rev-parse", "HEAD", cwd=path).strip()
    assert git.commit(path, "change fees", "pr:run-1:i1") == first
    assert git.create_branch("run-1", "i1") == (name, path)
    assert "+fees: {}" in git.diff(name) and git.base() != first


def test_dirty_worktree_from_a_crash_is_discarded(git):
    name, path = git.create_branch("run-1", "i2")
    (path / "payments" / "transfer.py").write_text("half written", encoding="utf-8")
    assert git.changed(path) == ["payments/transfer.py"]
    _, again = git.create_branch("run-1", "i2")
    assert git.changed(again) == [] and "half written" not in (again / "payments" / "transfer.py").read_text()


def test_agent_git_cannot_reach_a_repository_that_contains_the_sandbox(git, tmp_path):
    """The sandbox lives inside the coLEX project (itself a git repository). Two locks keep agents out of it."""
    outer = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=tmp_path, capture_output=True, text=True)
    assert outer.returncode == 0, "this test must run inside an outer git repository to mean anything"
    for cwd in (git.repo.parent, tmp_path, git.repo.parent.parent):          # lock 1: the class refuses the place
        with pytest.raises(ForbiddenGitOperation):
            git._git("status", cwd=cwd)
    stray = git.worktrees / "run-x" / "not-a-worktree"
    stray.mkdir(parents=True)
    with pytest.raises(GitError):                                            # allowed place, but no repository there
        git._git("rev-parse", "HEAD", cwd=stray)
    for cwd in (git.repo.parent, stray):                                     # lock 2: git itself cannot discover it
        seen = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, env=git.env(), capture_output=True)
        assert seen.returncode != 0
