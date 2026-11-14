"""Versioned, hot-reloadable configuration (brief §4.4). Secrets never live here."""
from __future__ import annotations

import difflib
import hashlib
import json
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from colex import db, settings
from colex.contracts import ConfigVersion
from colex.runtime import audit


class ConfigError(ValueError):
    """Readable validation error for the Settings page."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Budgets(_Strict):
    max_tokens_per_run: int = Field(gt=0)
    max_cost_usd_per_law: float = Field(gt=0)
    max_impact_steps: int = Field(gt=0, le=200)
    max_coder_iterations: int = Field(gt=0, le=10)
    max_grounding_retries: int = Field(ge=0, le=5)
    llm_max_attempts: int = Field(gt=0, le=8)
    llm_timeout_s: int = Field(gt=0, le=600)
    test_timeout_s: int = Field(gt=0, le=600)


class Triage(_Strict):
    relevance_threshold: float = Field(ge=0, le=1)
    borderline_band: float = Field(ge=0, le=0.5)


class Routing(_Strict):
    team_channels: dict[str, str]
    action_channels: dict[str, str] = Field(default_factory=dict)
    unknown_owner_channel: str
    review_channel: str
    approvers: dict[str, list[str]] = Field(default_factory=dict)
    mentions: dict[str, list[str]] = Field(default_factory=dict)


class MapCfg(_Strict):
    classification_threshold: float = Field(ge=0, le=1)
    max_items: int = Field(gt=0, le=500)
    max_chars: int = Field(gt=0)


class Schema(_Strict):
    models: dict[str, str]
    agent_models: dict[str, str]
    budgets: Budgets
    triage: Triage
    routing: Routing
    map: MapCfg
    connectors: dict[str, str]
    profile: dict[str, Any]
    prompt_versions: dict[str, str]
    console_url: str


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        schema = Schema.model_validate(payload)
    except ValidationError as exc:
        lines = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        raise ConfigError("Invalid configuration:\n" + "\n".join(lines)) from None
    for agent, role in schema.agent_models.items():
        if role not in schema.models:
            raise ConfigError(f"Invalid configuration:\nagent_models.{agent}: unknown model role '{role}'")
    return schema.model_dump()


class ConfigStore:
    def _row(self, r) -> ConfigVersion:
        return ConfigVersion(version_id=r["version_id"], hash=r["hash"], author=r["author"], ts=r["ts"],
                             diff=r["diff"], payload=json.loads(r["payload_json"]))

    def active(self) -> ConfigVersion:
        r = db.connect().execute("select * from config_versions order by seq desc limit 1").fetchone()
        if r is None:
            payload = yaml.safe_load((settings.CONFIG_DIR / "colex.yaml").read_text(encoding="utf-8"))
            return self.save(payload, author="config/colex.yaml")
        return self._row(r)

    def save(self, payload: dict[str, Any], author: str) -> ConfigVersion:
        payload = validate(payload)
        text = yaml.safe_dump(payload, sort_keys=True, allow_unicode=True)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        con = db.connect()
        con.execute("begin immediate")
        try:
            last = con.execute("select * from config_versions order by seq desc limit 1").fetchone()
            if last is not None and last["hash"] == digest:
                con.execute("commit")
                return self._row(last)
            seq = (last["seq"] + 1) if last else 1
            before = yaml.safe_dump(json.loads(last["payload_json"]), sort_keys=True, allow_unicode=True) if last else ""
            diff = "\n".join(difflib.unified_diff(before.splitlines(), text.splitlines(), "previous", f"cv-{seq}",
                                                  lineterm="", n=1))
            con.execute("insert into config_versions values(?,?,?,?,?,?,?)",
                        (f"cv-{seq}", digest, author, audit.now(), diff, db.dumps(payload), seq))
            con.execute("commit")
        except Exception:
            con.execute("rollback")
            raise
        audit.emit(None, "config", "save", "config", f"Config cv-{seq} saved by {author}", {"diff": diff[:4000]})
        return self.get(f"cv-{seq}")

    def rollback(self, version_id: str, author: str) -> ConfigVersion:
        """Re-save an old payload as a NEW version; history is never rewritten."""
        return self.save(self.get(version_id).payload, author=f"{author} (rollback to {version_id})")

    def get(self, version_id: str) -> ConfigVersion:
        r = db.connect().execute("select * from config_versions where version_id=?", (version_id,)).fetchone()
        if r is None:
            raise KeyError(version_id)
        return self._row(r)

    def history(self) -> list[ConfigVersion]:
        return [self._row(r) for r in db.connect().execute("select * from config_versions order by seq desc")]
