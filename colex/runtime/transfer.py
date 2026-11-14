"""Fork, export and import of checkpoints (brief §4.4, time travel)."""
from __future__ import annotations

import json
from typing import Any

from colex import db
from colex.contracts import Run
from colex.guardrails.redaction import mask
from colex.runtime import audit, store

BUNDLE_FORMAT = "colex-checkpoint-bundle/1"


class BundleError(ValueError):
    pass


class Transfer:
    def _snapshot(self, checkpoint_id: str) -> dict[str, Any]:
        """Everything a run knew up to and including this checkpoint."""
        cp = store.checkpoint(checkpoint_id)
        con = db.connect()
        cps = [dict(r) for r in con.execute("select * from checkpoints where run_id=? and seq<=? order by seq",
                                             (cp["run_id"], cp["seq"]))]
        keys = {c["step_key"] for c in cps}
        steps = [dict(r) for r in con.execute("select * from steps where run_id=?", (cp["run_id"],))
                 if r["step_key"] in keys]
        waits = [dict(r) for r in con.execute(
            "select * from waits where run_id=? and status='answered' and seq_answered<=?", (cp["run_id"], cp["seq"]))]
        refs = {s["output_ref"] for s in steps}
        blobs = {ref: con.execute("select body from blobs where ref=?", (ref,)).fetchone()["body"] for ref in refs}
        run = store.run_row(cp["run_id"])
        return {"format": BUNDLE_FORMAT, "checkpoint": cp, "law_id": run["law_id"], "meta": run["meta"],
                "map_version_id": run["map_version_id"], "steps": steps, "waits": waits, "blobs": blobs}

    def _restore(self, snap: dict[str, Any], config_version_id: str | None, origin: str) -> Run:
        cp = snap["checkpoint"]
        run = self.start_run(snap["law_id"], parent_checkpoint_id=cp["checkpoint_id"], meta=snap["meta"])
        new, old = run.run_id, cp["run_id"]
        con = db.connect()
        branches: dict[str, dict[str, str]] = {}
        for ref, body in snap["blobs"].items():
            con.execute("insert or ignore into blobs(ref,body) values(?,?)", (ref, mask(body)))
        for s in sorted(snap["steps"], key=lambda s: s["ts"]):
            checkpoint_id = self.checkpoint(new, s["branch_id"], s["node"], s["step_key"], s["output_ref"],
                                            s["config_version_id"])
            con.execute("insert into steps values(?,?,?,?,?,?,?,?,?)",
                        (new, s["step_key"], s["branch_id"], s["node"], "done", s["output_ref"], checkpoint_id,
                         s["config_version_id"], s["ts"]))
            branches[s["branch_id"]] = {"status": "running", "node": s["node"]}
        for w in snap["waits"]:
            con.execute("begin immediate")
            seq = store.next_seq(con)
            con.execute("insert into waits values(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (w["wait_id"].replace(old, new, 1), new, w["branch_id"], w["kind"], w["payload_json"],
                         "answered", w["answer_json"], w["actor"], w["created_ts"], w["answered_ts"], seq, seq))
            con.execute("commit")
        row = store.run_row(new)
        row["branches"], row["map_version_id"] = branches, snap["map_version_id"]
        row["current_node"] = branches.get("main", {}).get("node", "WATCH")
        if config_version_id:
            row["config_version_id"] = config_version_id
        store.save_run(row)
        audit.emit(new, "runtime", cp["node"], "run",
                   f"{origin} from checkpoint {cp['checkpoint_id']} ({cp['node']}) of {old}",
                   {"parent_checkpoint_id": cp["checkpoint_id"], "parent_run_id": old})
        return self.get_run(new)

    def fork(self, checkpoint_id: str, *, config_version_id: str | None = None) -> Run:
        """New run that replays the parent up to the checkpoint. The parent run is never modified."""
        return self._restore(self._snapshot(checkpoint_id), config_version_id, "Forked")

    def export_checkpoint(self, checkpoint_id: str) -> bytes:
        """JSON bundle. Stored blobs are already masked; the bundle is masked again as a whole."""
        return mask(json.dumps(self._snapshot(checkpoint_id), ensure_ascii=False, indent=1)).encode("utf-8")

    def import_checkpoint(self, bundle: bytes) -> Run:
        try:
            snap = json.loads(bundle.decode("utf-8"))
            if snap.get("format") != BUNDLE_FORMAT:
                raise BundleError("not a coLEX checkpoint bundle")
            for key in ("checkpoint", "law_id", "meta", "steps", "waits", "blobs"):
                if key not in snap:
                    raise BundleError(f"bundle is missing '{key}'")
            missing = {s["output_ref"] for s in snap["steps"]} - set(snap["blobs"])
            if missing:
                raise BundleError("bundle is missing step outputs")
            for body in snap["blobs"].values():
                json.loads(body)
        except BundleError:
            raise
        except Exception as exc:
            raise BundleError(f"malformed bundle: {type(exc).__name__}") from None
        return self._restore(snap, None, "Imported")
