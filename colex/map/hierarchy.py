"""The map hierarchy: taxonomy nodes (L0–L3), rules, and the choice of a primary path per resource.

The L3 topic is chosen by keyword scoring against the closed taxonomy (deterministic, D-019).
Below the confidence threshold a resource goes to the Unclassified queue instead of being guessed.
"""
from __future__ import annotations

import fnmatch
import hashlib
import re
from typing import Any

SEP = " › "
SINGLE_TOPIC_CONFIDENCE = 0.9


def node_id(path: str) -> str:
    return "n-" + hashlib.sha1(path.encode("utf-8")).hexdigest()[:10]


def norm_path(path: str) -> str:
    """Accept '›', '>' or '/' as separators and any spacing."""
    parts = [p.strip() for p in re.split(r"\s*(?:›|>|/)\s*", path or "") if p.strip()]
    return SEP.join(parts)


def nodes(tax: dict[str, Any]) -> list[dict[str, Any]]:
    root = tax["company"]
    out = [{"path": root, "parent": None, "level": "L0", "name": root}]
    for l1, domains in tax["areas"].items():
        out.append({"path": SEP.join([root, l1]), "parent": root, "level": "L1", "name": l1})
        for l2, topics in domains.items():
            out.append({"path": SEP.join([root, l1, l2]), "parent": SEP.join([root, l1]), "level": "L2", "name": l2})
            for l3 in topics:
                out.append({"path": SEP.join([root, l1, l2, l3]), "parent": SEP.join([root, l1, l2]),
                            "level": "L3", "name": l3})
    return out


def topics(tax: dict[str, Any], l1: str | None, l2: str | None) -> list[tuple[str, list[str]]]:
    out = []
    for a, domains in tax["areas"].items():
        for d, ts in domains.items():
            if (l1 is None or a == l1) and (l2 is None or d == l2):
                out += [(SEP.join([tax["company"], a, d, t]), kws) for t, kws in ts.items()]
    return out


def rule_for(uri: str, title: str, text: str, rules: list[dict[str, Any]]) -> dict[str, Any]:
    for rule in rules:
        if (fnmatch.fnmatch(uri, rule["glob"]) and re.search(rule.get("title", ""), title)
                and re.search(rule.get("text", ""), text)):
            return rule
    return {"info_type": "page"}


def assign(uri: str, title: str, text: str, rule: dict[str, Any], tax: dict[str, Any],
           learned: list[dict[str, str]]) -> dict[str, Any]:
    """Primary path, confidence and the reason, for one resource."""
    for item in learned:   # human assignments from the Unclassified queue win
        if fnmatch.fnmatch(uri, item["glob"]):
            return {"path": item["node_path"], "confidence": 1.0, "reason": f"human assignment by {item['author']}"}
    candidates = topics(tax, rule.get("l1"), rule.get("l2"))
    if not candidates:
        return {"path": None, "confidence": 0.0, "reason": "rule points outside the taxonomy"}
    scored = []
    heading = f"{uri.rsplit('/', 1)[-1]} {title}"
    for path, keywords in candidates:
        score = 0
        for kw in keywords:
            score += min(len(re.findall(kw, text, re.I)), 3)
            score += 3 if re.search(kw, heading, re.I) else 0
        scored.append((score, path))
    scored.sort(reverse=True)
    top, path = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0
    fixed = "rule " + rule["glob"] if "glob" in rule else "no rule"
    if len(candidates) == 1 and rule.get("l2"):
        return {"path": path, "confidence": SINGLE_TOPIC_CONFIDENCE, "reason": f"{fixed}: only topic of {rule['l2']}"}
    if top == 0:
        return {"path": None, "confidence": 0.0, "reason": f"{fixed}: no topic keyword matched"}
    confidence = round(top / (top + second), 2) if second else SINGLE_TOPIC_CONFIDENCE
    runner = f", next: {scored[1][1].split(SEP)[-1]} ({second})" if second else ""
    return {"path": path, "confidence": confidence,
            "reason": f"{fixed}: keyword score {top} for {path.split(SEP)[-1]}{runner}"}
