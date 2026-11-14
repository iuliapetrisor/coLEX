"""Block Kit builders (brief §4.5). Pure functions: data in, Slack blocks out. No chat imitation anywhere.

Slack limits respected here: at most 50 blocks per message, section text at most 3000 characters,
button text at most 75, unique action ids per message. Long batches are cut with a link to the Console.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

SLACK_USER = re.compile(r"[UW][A-Z0-9]{2,}")

MAX_BLOCKS, MAX_TEXT, MAX_BUTTON, MAX_ITEMS = 50, 2900, 70, 12
TODO = {"CONTRACT_REVIEW": "Review the contract", "TERMS_UPDATE": "Update the customer terms",
        "FEE_CHANGE": "Change the fee schedule", "POLICY_UPDATE": "Update the procedure",
        "CODE_CHANGE": "Code change (coLEX opens a PR for review)",
        "CONFIG_CHANGE": "Configuration change (coLEX opens a PR for review)"}


def esc(text: str) -> str:
    """Escape text for mrkdwn so document content cannot create mentions or links."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def cut(text: str, limit: int = MAX_TEXT) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def section(text: str) -> dict[str, Any]:
    return {"type": "section", "text": {"type": "mrkdwn", "text": cut(text)}}


def context(text: str) -> dict[str, Any]:
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": cut(text, 1900)}]}


def button(text: str, action_id: str, value: str, style: str | None = None) -> dict[str, Any]:
    out = {"type": "button", "action_id": action_id, "value": cut(value, 1900),
           "text": {"type": "plain_text", "text": cut(text, MAX_BUTTON), "emoji": True}}
    if style:
        out["style"] = style
    return out


def evidence_url(console: str, uri: str, start: int, end: int) -> str:
    return f"{console}/evidence?uri={quote(uri, safe='')}&start={start}&end={end}"


def mentions(cfg: dict[str, Any], team: str | None) -> str:
    return " ".join(f"<@{u}>" for u in cfg["routing"]["mentions"].get(team or "", []))


def decided(blocks: list[dict[str, Any]], decision: str, actor: str, when: str) -> list[dict[str, Any]]:
    """The same message with its buttons replaced by the decision, who decided and when."""
    kept = [b for b in blocks if b.get("type") != "actions"]
    who = f"<@{actor}>" if SLACK_USER.fullmatch(actor) else esc(actor)   # mention only real Slack user ids
    return kept[: MAX_BLOCKS - 1] + [context(f"*Decision:* {esc(decision)} · by {who} · {esc(when)}")]


def notification(batch: dict[str, Any], cfg: dict[str, Any], run_id: str, idem_key: str) -> list[dict[str, Any]]:
    """One batch per team: law + article, one section per item with evidence link, deadline, owner; buttons."""
    console = cfg["console_url"]
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": cut(batch["title"], 140)}},
              section(esc(batch["body"]))]
    items = batch["items"]
    for item in items[:MAX_ITEMS]:
        lines = item["lines"]
        link = evidence_url(console, item["resource_uri"], lines["start"], lines["end"])
        owner = mentions(cfg, item.get("owner_team")) or (f"team {esc(item['owner_team'])}" if item.get("owner_team")
                                                          else ":warning: *owner unknown, please assign*")
        deadline = f" · deadline *{item['deadline']}*" if item.get("deadline") else ""
        blocks.append(section(
            f"*{TODO.get(item['action'], item['action'])}*{deadline}\n{esc(item.get('obligation') or '')}\n"
            f"<{link}|{esc(item['resource_uri'])}:{lines['start']}-{lines['end']}> · {esc(item['citation'])} · {owner}\n"
            f"> {esc(cut(item['evidence'], 300))}"))
    if len(items) > MAX_ITEMS:
        blocks.append(context(f"{len(items) - MAX_ITEMS} more item(s): <{console}/runs/{run_id}|open the run in the "
                              "Console>"))
    blocks.append({"type": "actions", "block_id": "notification", "elements": [
        button("Acknowledge", "colex_ack", idem_key, "primary"), button("Assign to me", "colex_assign", idem_key),
        button("Dispute", "colex_dispute", idem_key, "danger")]})
    blocks.append(context(f"coLEX · decision support, not legal advice · <{console}/runs/{run_id}|run {run_id}> · "
                          "PayRo SRL is fictional demo data"))
    return blocks[:MAX_BLOCKS]


def question(payload: dict[str, Any], cfg: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    """Legal question: the ambiguity, the cited excerpt, one button per option, and 'Answer in detail' (modal)."""
    q, wait_id = payload["question"], payload["wait_id"]
    who = mentions(cfg, q["to_team"])
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": "coLEX needs an answer from legal"}},
              section(f"{who + ' ' if who else ''}*{esc(q['text'])}*")]
    if payload.get("citation"):
        blocks.append(context(esc(payload["citation"])))
    if payload.get("excerpt"):
        blocks.append(section("> " + esc(cut(payload["excerpt"], 600)).replace("\n", "\n> ")))
    if q["blocking_items"]:
        blocks.append(context(f"Waiting on this answer: {len(q['blocking_items'])} item(s). The rest of the run "
                              "continues."))
    elements = [button(option, f"colex_answer_{n}", f"{wait_id}|{option}") for n, option in enumerate(q["options"][:4])]
    elements.append(button("Answer in detail", "colex_answer_detail", wait_id))
    blocks.append({"type": "actions", "block_id": "question", "elements": elements})
    blocks.append(context(f"Only mapped legal approvers can answer · <{cfg['console_url']}/runs/{run_id}|run {run_id}>"))
    return blocks
