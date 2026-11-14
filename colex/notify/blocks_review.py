"""Block Kit builders for the PR review message, the run status reply and the two modals."""
from __future__ import annotations

from typing import Any

from colex.notify.blocks import button, context, cut, esc, mentions, section

MERGE_NOTE = "coLEX never merges. Approving records your decision; merging stays a manual human step."


def _tests(suite: dict[str, Any] | None) -> str:
    return "not run" if not suite else f"{suite['passed']} pass / {suite['failed'] + suite['errors']} fail"


def diff_stat(diff: str) -> str:
    files = [line[6:] for line in diff.splitlines() if line.startswith("+++ b/")]
    added = sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))
    return f"{len(files)} file(s) ({', '.join(files[:4])}) · +{added} / -{removed}"


def review(payload: dict[str, Any], cfg: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    """PR review: diff summary, tests before and after, iterations, Console diff link, Approve / Request changes."""
    change, ctx, wait_id = payload["change"], payload["context"], payload["wait_id"]
    item = ctx["item"]
    console = cfg["console_url"]
    who = mentions(cfg, "payments-eng")
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "coLEX opened a change for review"}},
        section(f"{who + ' ' if who else ''}*{esc(ctx.get('summary') or 'Code change')}*\n"
                f"{esc(item.get('obligation') or '')}\n{esc(item['citation'])}"),
        section(f"*Branch* `{esc(change['branch'])}`\n*Diff* {esc(diff_stat(change['diff']))}\n"
                f"*Tests before* {_tests(change['tests_before'])} → *after* {_tests(change['tests_after'])}\n"
                f"*Attempts* {change['iterations']} · review round {ctx.get('round', 1)}"),
        section(f"<{console}/changes/{wait_id}|Open the full diff in the Console>"),
        {"type": "actions", "block_id": "review", "elements": [
            button("Approve", "colex_approve", wait_id, "primary"),
            button("Request changes", "colex_request_changes", wait_id, "danger")]},
        context(f"{MERGE_NOTE} Only mapped engineer approvers can decide · <{console}/runs/{run_id}|run {run_id}>"),
    ]
    return blocks


def status(text: str) -> list[dict[str, Any]]:
    return [context(esc(cut(text, 1800)))]


def modal(kind: str, wait_id: str, title: str, label: str, channel: str, ts: str) -> dict[str, Any]:
    """Modal with one multiline input. kind: 'answer' (legal question) or 'changes' (request changes)."""
    return {
        "type": "modal", "callback_id": f"colex_modal_{kind}",
        "private_metadata": f"{wait_id}|{channel}|{ts}",
        "title": {"type": "plain_text", "text": cut(title, 24)},
        "submit": {"type": "plain_text", "text": "Send"}, "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [{"type": "input", "block_id": "body", "label": {"type": "plain_text", "text": cut(label, 150)},
                    "element": {"type": "plain_text_input", "action_id": "text", "multiline": True,
                                "max_length": 2000}}],
    }


def render(kind: str, payload: dict[str, Any], cfg: dict[str, Any], run_id: str, idem_key: str) -> tuple[str, list]:
    """Fallback text and blocks for an outbox row."""
    from colex.notify import blocks as b
    if kind == "notification":
        return payload["title"], b.notification(payload, cfg, run_id, idem_key)
    if kind == "question":
        return "coLEX needs an answer from legal: " + payload["question"]["text"], b.question(payload, cfg, run_id)
    if kind == "review":
        return "coLEX opened a change for review: " + payload["change"]["branch"], review(payload, cfg, run_id)
    return payload["text"], status(payload["text"])
