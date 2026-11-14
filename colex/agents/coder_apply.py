"""Coder helpers: which files may be edited, which tests are the target, applying edit blocks safely."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

MAX_FILES = 4
FAILURE_LINES = 30


class Edit(BaseModel):
    path: str
    search: str = Field(min_length=1)
    replace: str


class Patch(BaseModel):
    summary: str = Field(min_length=1)
    edits: list[Edit]


class PatchError(ValueError):
    """Why a patch was refused; the message goes back to the model."""


def repo_path(uri: str) -> str:
    return uri.split("://", 1)[1]


def editable(tools, uri: str) -> list[str]:
    """The item's file plus repository files one link away (depends_on, implements). Never the whole repo."""
    paths = [repo_path(uri)]
    for link in tools.related(uri, ["depends_on", "implements"]).get("items", []):
        for other in (link["from"], link["to"]):
            if other.startswith("repo://") and repo_path(other) not in paths:
                paths.append(repo_path(other))
    return paths[:MAX_FILES]


def targets(worktree: Path, item_path: str, failing: list[str]) -> list[str]:
    """Failing tests whose test file uses the module being changed."""
    stem = Path(item_path).stem
    pattern = re.compile(rf"\bpayments\.{stem}\b|from payments import [^\n]*\b{stem}\b")
    out = []
    for test_id in failing:
        file = worktree / test_id.split("::")[0]
        if file.is_file() and pattern.search(file.read_text(encoding="utf-8")):
            out.append(test_id)
    return out


def apply(worktree: Path, patch: Patch, allowed: list[str]) -> None:
    """Apply search/replace blocks. All-or-nothing per call: raises PatchError before a partial write."""
    if not patch.edits:
        raise PatchError("the patch has no edits")
    contents: dict[str, str] = {}
    for edit in patch.edits:
        if edit.path not in allowed:
            raise PatchError(f"'{edit.path}' is not editable. Editable files: {', '.join(allowed)}. "
                             "Tests can never be edited.")
        text = contents.get(edit.path)
        if text is None:
            text = (worktree / edit.path).read_text(encoding="utf-8")
        count = text.count(edit.search)
        if count != 1:
            raise PatchError(f"in {edit.path} the search text occurs {count} times; it must occur exactly once. "
                             "Copy it exactly from the current file content.")
        contents[edit.path] = text.replace(edit.search, edit.replace)
    for path, text in contents.items():
        (worktree / path).write_text(text, encoding="utf-8")


def failure_text(result: dict[str, Any], wanted: list[str]) -> str:
    """Trimmed failure for the model: test name + assertion, at most 30 lines per test."""
    if result["timed_out"]:
        return "The test run timed out: the change makes a test hang."
    if result["unusable"]:
        return "The tests could not be collected (syntax or import error):\n" + result["output_tail"][-1500:]
    parts = []
    for test_id in wanted[:4]:
        lines = result["details"].get(test_id, "").splitlines()[:FAILURE_LINES]
        parts.append(f"FAILED {test_id}\n" + "\n".join(lines))
    return "\n\n".join(parts)
