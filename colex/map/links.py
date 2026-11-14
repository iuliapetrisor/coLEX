"""Typed cross-links between resources, each with its evidence (uri + lines), and secondary memberships."""
from __future__ import annotations

import ast
import re
from typing import Any

from colex.map.hierarchy import SEP

TICKET = re.compile(r"\b([A-Z]{2,6}-\d+)\b")
CODE_REF = re.compile(r"`([\w/.-]+\.(?:py|ya?ml))`")
SAME_OWNER_CAP = 40


def build(resources: dict[str, dict[str, Any]]) -> tuple[list[tuple], list[tuple]]:
    """Returns (edges, secondary memberships). An edge is (src, dst, kind, ev_uri, ev_start, ev_end)."""
    edges: list[tuple] = []
    by_path = {f"{r['source']}://{r['path']}": uri for uri, r in resources.items()}
    by_stem = {r["path"].rsplit("/", 1)[-1].rsplit(".", 1)[0]: uri for uri, r in resources.items()}
    contracts = {r["facts"]["counterparty_id"]: uri for uri, r in resources.items()
                 if r["info_type"] == "contract" and r["facts"].get("counterparty_id")}

    for uri, r in resources.items():
        lines = r["text"].splitlines()
        # depends_on: Python imports inside the repository
        if r["path"].endswith(".py"):
            try:
                tree = ast.parse(r["text"])
            except SyntaxError:
                tree = ast.Module(body=[], type_ignores=[])
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    names = [f"{node.module}.{a.name}" for a in node.names] + [node.module]
                elif isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                for name in names:
                    target = by_path.get(f"repo://{name.replace('.', '/')}.py")
                    if target and target != uri:
                        edges.append((uri, target, "depends_on", uri, node.lineno, node.lineno))
            for number, line in enumerate(lines, 1):   # config files a module reads
                for m in re.finditer(r"[\"']([\w.-]+\.ya?ml)[\"']", line):
                    target = by_path.get(f"repo://{r['path'].rsplit('/', 1)[0]}/{m.group(1)}")
                    if target:
                        edges.append((uri, target, "depends_on", uri, number, number))
        # references: ticket keys and code paths mentioned in documents
        for number, line in enumerate(lines, 1):
            for m in TICKET.finditer(line):
                target = by_stem.get(m.group(1))
                if target and target != uri:
                    edges.append((uri, target, "references", uri, number, number))
            for m in CODE_REF.finditer(line):
                target = by_path.get(f"repo://{m.group(1)}")
                if target and target != uri and r["info_type"] != "code":
                    edges.append((uri, target, "references", uri, number, number))
        # governed_by: a resource that uses a provider → that provider's contract
        for cp_id, line in r["mentions"]:
            contract = contracts.get(cp_id)
            if contract and contract != uri and r["info_type"] in ("code", "config"):
                edges.append((uri, contract, "governed_by", uri, line, line))

    # implements: a fee in code or config equals a fee published in a document
    fees: dict[str, list[tuple[str, int]]] = {}
    for uri, r in resources.items():
        for e in r["entities"]:
            if e["etype"] == "fee":
                fees.setdefault(e["value"], []).append((uri, e["line"]))
    for value, places in fees.items():
        docs = [(u, ln) for u, ln in places if resources[u]["info_type"] in ("fee_schedule", "customer_terms")]
        for src, line in places:
            if resources[src]["info_type"] in ("config", "code"):
                edges += [(src, doc, "implements", src, line, line) for doc, _ in docs]

    # same_counterparty: every mention links to the contract (star, not clique)
    for uri, r in resources.items():
        for cp_id in sorted({c for c, _ in r["mentions"]}):
            contract = contracts.get(cp_id)
            if contract and contract != uri:
                line = next(ln for c, ln in r["mentions"] if c == cp_id)
                edges.append((uri, contract, "same_counterparty", uri, line, line))

    # same_owner: chain per team, capped, used to batch notifications
    owners: dict[str, list[str]] = {}
    for uri, r in resources.items():
        if r["owner"]["owner_team"]:
            owners.setdefault(r["owner"]["owner_team"], []).append(uri)
    for uris in owners.values():
        for a, b in list(zip(uris, uris[1:]))[:SAME_OWNER_CAP]:
            edges.append((a, b, "same_owner", a, 1, 1))

    edges = sorted(set(edges))
    # secondary membership: a strong link (implements, references from a ticket) to a resource in another branch
    secondary = set()
    for src, dst, kind, *_ in edges:
        a, b = resources[src]["primary_path"], resources[dst]["primary_path"]
        if kind == "implements" and a and b and SEP.join(a.split(SEP)[:3]) != SEP.join(b.split(SEP)[:3]):
            secondary.add((src, b))
    return edges, sorted(secondary)
