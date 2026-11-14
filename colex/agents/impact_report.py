"""Reporting half of the Impact Analyst dispatcher: validated impact items and questions to legal."""
from __future__ import annotations

from typing import Any

from colex.contracts import ImpactItem
from colex.guardrails.validators import Rejected, check_item

MAX_QUESTIONS = 3


class Reporting:
    def report(self, args: dict[str, Any]) -> dict[str, Any]:
        uri = str(args.get("resource_uri"))
        try:
            if self.scope is not None and uri not in self.scope:
                raise Rejected("outside the scope of this re-plan; report only the resource in question and its links")
            if uri not in {u for u, _, _ in self.tools.meter["read"]}:
                raise Rejected("read the lines with read() before reporting them")
            fields = check_item(args, self.law, self.flagged, self.tools)
        except Rejected as exc:
            key = (uri, args.get("action"))
            count = self.rejections[key] = self.rejections.get(key, 0) + 1
            self.ctx.emit("retry", f"Grounding validator rejected an item for {uri}: {exc}")
            if count > self.ctx.config["budgets"]["max_grounding_retries"]:
                self.dropped.append({"resource_uri": uri, "reason": str(exc)})
                self.ctx.emit("escalation", f"Dropped an item for {uri} after {count} failed attempts: {exc}")
                return {"error": f"rejected and dropped: {exc}. Do not report this item again."}
            return {"error": f"rejected: {exc}"}
        for item in self.items:   # the same place reported twice is one item
            same = (item["resource_uri"], item["action"], item["article_id"]) == \
                   (uri, fields["action"], fields["article_id"])
            if same and item["lines"]["start"] <= fields["lines"]["end"] \
                    and fields["lines"]["start"] <= item["lines"]["end"]:
                return {"ok": True, "item_id": item["item_id"], "note": "already reported"}
        card = self.tools.card(uri)
        item = ImpactItem(item_id=f"{self.prefix}i{len(self.items) + 1}", owner_team=card["owner_team"], **fields)
        self.items.append({**item.model_dump(mode="json"), "breadcrumbs": card["primary_path"],
                           "legal_steward": card["legal_steward"], "ownership_source": card["ownership_source"]})
        owner = card["owner_team"] or "owner unknown"
        self.ctx.emit("impact", f"{item.action} · {uri}:{item.lines.start}-{item.lines.end} · {item.citation} · "
                                f"{owner}", {"item": item.model_dump(mode="json")})
        return {"ok": True, "item_id": item.item_id}

    def ask(self, args: dict[str, Any]) -> dict[str, Any]:
        uri = args.get("resource_uri") if isinstance(args.get("resource_uri"), str) else None
        if uri and any(q["resource_uri"] == uri for q in self.questions):
            return {"ok": True, "note": "a question about this resource is already open"}
        if len(self.questions) >= MAX_QUESTIONS:
            return {"error": "question limit reached; continue with what the documents establish"}
        text = str(args.get("question", "")).strip()
        raw = args.get("options") if isinstance(args.get("options"), list) else []
        options = list(dict.fromkeys(str(o).strip()[:70] for o in raw if str(o).strip()))[:4]
        if len(text) < 10 or len(options) < 2:
            return {"error": "ask_legal needs a question and 2 to 4 distinct options"}
        known = {i["item_id"] for i in self.items}
        named = args.get("blocking_item_ids") if isinstance(args.get("blocking_item_ids"), list) else []
        blocking = sorted({b for b in named if b in known}
                          | {i["item_id"] for i in self.items if uri and i["resource_uri"] == uri})
        lines, excerpt = (self.tools.lines(uri) if uri else None), ""
        start, end = args.get("start"), args.get("end")
        if lines and isinstance(start, int) and isinstance(end, int) and 1 <= start <= end:
            excerpt = "\n".join(lines[start - 1:min(end, start + 7)])[:500]
        article = args.get("article_id") if args.get("article_id") in {a.id for a in self.law.articles} else None
        qid = f"{self.prefix}q{len(self.questions) + 1}"
        self.questions.append({
            "id": qid, "resource_uri": uri, "excerpt": excerpt,
            "citation": f"CELEX:{self.law.celex}" + (f" {article}" if article else ""),
            "question": {"to_team": "legal", "text": text[:500], "options": options, "blocking_items": blocking}})
        self.ctx.emit("rationale", f"Missing information → asking legal: {text[:160]}", {"question_id": qid})
        return {"ok": True, "question_id": qid, "note": "Legal will answer. Continue with the other work."}
