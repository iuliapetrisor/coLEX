"""Connectors: one read-only interface for every company source (brief §2).

Each source is a folder in the sandbox. No write method exists on any connector.
Path parts starting with "_" are never listed (source metadata files, hidden evaluation data).
"""
from __future__ import annotations

import fnmatch
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

SOURCES = ("onedrive", "gdrive", "confluence", "jira", "intranet", "repo")
TEXT_SUFFIXES = {".md", ".txt", ".py", ".yaml", ".yml", ".json"}
SKIP_DIRS = {"tests"}
SKIP_NAMES = {"conftest.py", "CODEOWNERS"}   # test harness and ownership metadata, not company knowledge


class ConnectorError(RuntimeError):
    """A source could not be read. The map build fails and the previous map stays active."""


@dataclass
class RawRef:
    uri: str
    source: str
    path: str
    sha: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawResource:
    ref: RawRef
    text: str


class Connector(ABC):
    source: str

    @abstractmethod
    def list(self) -> Iterable[RawRef]: ...

    @abstractmethod
    def fetch(self, ref: RawRef) -> RawResource: ...


def normalize(raw: bytes) -> str:
    """Bytes → text with stable 1-based lines: BOM removed, CRLF → LF, cedilla diacritics → comma-below."""
    text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    return text.translate(str.maketrans("şţŞŢ", "șțȘȚ"))


class FolderConnector(Connector):
    """Reads one sandbox folder. Owner metadata comes from `_meta.yaml` (stand-in for the source system)."""

    def __init__(self, source: str, root: Path) -> None:
        self.source, self.root = source, Path(root)

    def _owners(self) -> list[tuple[str, dict[str, Any]]]:
        meta = self.root / "_meta.yaml"
        if not meta.is_file():
            return []
        owners = (yaml.safe_load(meta.read_text(encoding="utf-8")) or {}).get("owners", {})
        return sorted(owners.items(), key=lambda kv: -len(kv[0]))   # longest prefix first

    def _metadata(self, rel: str, owners: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
        for prefix, owner in owners:
            if rel.startswith(prefix):
                return {"owner_team": owner.get("team"), "owner_role": owner.get("role"),
                        "approver_role": owner.get("approver"), "legal_steward": owner.get("steward"),
                        "owner_origin": f"{self.source} owner metadata"}
        return {}

    def list(self) -> Iterable[RawRef]:
        if not self.root.is_dir():
            raise ConnectorError(f"{self.source}: folder {self.root} does not exist")
        owners = self._owners()
        for path in sorted(self.root.rglob("*")):
            rel = path.relative_to(self.root)
            if (not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES
                    or any(part.startswith(("_", ".")) for part in rel.parts) or SKIP_DIRS & set(rel.parts[:-1])
                    or rel.name in SKIP_NAMES):
                continue
            posix = rel.as_posix()
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            yield RawRef(f"{self.source}://{posix}", self.source, posix, sha, self._metadata(posix, owners))

    def fetch(self, ref: RawRef) -> RawResource:
        path = self.root / ref.path
        try:
            return RawResource(ref, normalize(path.read_bytes()))
        except FileNotFoundError:
            raise ConnectorError(f"{ref.uri}: deleted between list and fetch") from None
        except UnicodeDecodeError:
            raise ConnectorError(f"{ref.uri}: not UTF-8 text") from None


class RepoConnector(FolderConnector):
    """Git-style repository: owners come from CODEOWNERS (last matching pattern wins)."""

    def _owners(self) -> list[tuple[str, dict[str, Any]]]:
        file = self.root / "CODEOWNERS"
        rules = []
        if file.is_file():
            for line in file.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) >= 2 and not line.startswith("#"):
                    rules.append((parts[0], {"team": parts[1].split("/")[-1].lstrip("@")}))
        return rules[::-1]

    def _metadata(self, rel: str, owners):
        for pattern, owner in owners:
            if rel == pattern or rel.startswith(pattern.rstrip("/") + "/") or fnmatch.fnmatch(rel, pattern):
                return {"owner_team": owner["team"], "owner_origin": "CODEOWNERS"}
        return {}


def connectors(cfg: dict[str, Any], root: Path) -> list[Connector]:
    out: list[Connector] = []
    for source, folder in cfg["connectors"].items():
        if source not in SOURCES:
            raise ConnectorError(f"unknown connector '{source}'")
        cls = RepoConnector if source == "repo" else FolderConnector
        out.append(cls(source, root / folder))
    return out
