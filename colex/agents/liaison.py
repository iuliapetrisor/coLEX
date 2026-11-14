"""Liaison: turns impact items into one notification batch per channel, routed by ownership."""
from __future__ import annotations

from typing import Any

from colex.contracts import ImpactItem, LawDocument, Notification

ACTIONS = ["acknowledge", "assign", "dispute"]
TODO = {
    "CONTRACT_REVIEW": "Review and amend the contract",
    "TERMS_UPDATE": "Update the customer terms",
    "FEE_CHANGE": "Change the fee",
    "POLICY_UPDATE": "Update the policy or procedure",
    "CODE_CHANGE": "Change the code (coLEX will open a PR for review)",
    "CONFIG_CHANGE": "Change the configuration (coLEX will open a PR for review)",
}


def channel_for(cfg: dict[str, Any], item: ImpactItem) -> tuple[str, bool]:
    """Channel for an item and whether its owner is unknown. Action routing wins over team routing."""
    routing = cfg["routing"]
    if item.action in routing["action_channels"]:
        return routing["action_channels"][item.action], item.owner_team is None
    if item.owner_team and item.owner_team in routing["team_channels"]:
        return routing["team_channels"][item.owner_team], False
    return routing["unknown_owner_channel"], True


def plan(cfg: dict[str, Any], law: LawDocument, items: list[ImpactItem], label: str = "") -> list[Notification]:
    groups: dict[str, list[ImpactItem]] = {}
    unknown: dict[str, int] = {}
    for item in items:
        if item.action == "NO_ACTION":
            continue
        channel, owner_unknown = channel_for(cfg, item)
        groups.setdefault(channel, []).append(item)
        unknown[channel] = unknown.get(channel, 0) + int(owner_unknown)
    batches = []
    for channel, batch in sorted(groups.items()):
        deadlines = sorted({i.deadline.isoformat() for i in batch if i.deadline})
        body = f"{len(batch)} item(s) need action under {law.title[:140]}."
        if deadlines:
            body += f" Earliest deadline: {deadlines[0]}."
        if unknown[channel]:
            body += f" {unknown[channel]} item(s) have no known owner: please assign one."
        if law.fictional:
            body = "FICTIONAL – DEMO ONLY. " + body
        batches.append(Notification(channel=channel, title=f"{label}CELEX {law.celex}: action needed",
                                    body=body, items=batch, actions=ACTIONS))
    return batches
