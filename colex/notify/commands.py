"""`/colex` commands and @coLEX mentions. Deterministic: answers come from the run store and audit trail."""
from __future__ import annotations

from typing import Any

from colex import db
from colex.runtime import audit, store

USAGE = "Usage: `/colex status` · `/colex why <item> [run]` · `/colex pause <run>` · `/colex resume <run>`"


def runs(limit: int = 8) -> list[dict[str, Any]]:
    rows = db.connect().execute("select r.run_id, r.law_id, r.status, r.paused, l.title, l.status law_status "
                                "from runs r left join laws l on l.celex=r.law_id order by r.created_ts desc")
    out = [dict(r) for r in rows if r["law_status"] != "archived"]
    return out[:limit]


def status() -> str:
    found = runs()
    if not found:
        return "coLEX is online. No relevant act is being processed."
    lines = []
    for r in found:
        waits = len(store.waits(r["run_id"], "pending"))
        extra = f" · waiting for {waits} human decision(s)" if waits else ""
        lines.append(f"• `{r['run_id']}` CELEX {r['law_id']}: *{'paused' if r['paused'] else r['status']}*{extra}")
    return "coLEX runs:\n" + "\n".join(lines)


def items(run_id: str) -> list[dict[str, Any]]:
    """Every impact item a run produced (analysis, re-plans, register)."""
    out = []
    rows = db.connect().execute("select output_ref from steps where run_id=? and status='done' and "
                                "node in ('IMPACT','REGISTER') order by ts", (run_id,))
    for r in rows:
        out += store.get_blob(r["output_ref"]).get("items", [])
    return out


def why(item_id: str, run_id: str | None = None) -> str:
    """Evidence, citation and the reasoning trail for one item."""
    for candidate in ([run_id] if run_id else [r["run_id"] for r in runs(50)]):
        try:
            found = next((i for i in items(candidate) if i["item_id"] == item_id), None)
        except KeyError:
            continue
        if found:
            lines = found["lines"]
            trail = [e["summary"] for e in audit.events(candidate) if e["kind"] == "rationale"
                     and found["resource_uri"] in str(e["detail"])][-4:]
            return (f"*{found['action']}* · `{found['resource_uri']}:{lines['start']}-{lines['end']}` · "
                    f"{found['citation']}\n{found.get('obligation', '')}\n> {found['evidence'][:300]}\n"
                    + ("Reasoning trail:\n" + "\n".join(f"• {t[:200]}" for t in trail) if trail else "")
                    + f"\nRun `{candidate}`. Decision support, not legal advice.")
    return f"No item `{item_id}` found" + (f" in run `{run_id}`." if run_id else " in the recent runs.")


def command(rt, text: str, user: str) -> str:
    parts = (text or "status").split()
    verb, args = parts[0].lower(), parts[1:]
    if verb == "status":
        return status()
    if verb == "why" and args:
        return why(args[0], args[1] if len(args) > 1 else None)
    if verb in ("pause", "resume") and args:
        cfg = rt.configs.active().payload
        if not any(user in ids for ids in cfg["routing"]["approvers"].values()):
            audit.emit(None, "slack", "-", "human", f"Refused {user}: {verb} needs an approver")
            return "Only mapped approvers can pause or resume a run."
        try:
            store.run_row(args[0])
        except KeyError:
            return f"Unknown run `{args[0]}`."
        (rt.pause if verb == "pause" else rt.resume)(args[0], actor=user)
        return f"Run `{args[0]}` {'paused' if verb == 'pause' else 'resumed'}."
    return USAGE


def mention(text: str) -> str:
    """@coLEX: a status answer from the audit data. No model call (scope cut)."""
    return status() + "\nAsk `/colex why <item>` for the evidence behind an item."
