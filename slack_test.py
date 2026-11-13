"""
slack_test.py - verifica integrarea coLEX cu Slack (Socket Mode, fara tunel public).

  pip install slack_bolt python-dotenv
  # in .env:
  #   SLACK_BOT_TOKEN=xoxb-...
  #   SLACK_APP_TOKEN=xapp-...
  python slack_test.py

Posteaza in #legal un card cu doua butoane. Cand cineva apasa un buton,
cardul se actualizeaza cu decizia, cine a decis si cand.
"""
import os
from datetime import datetime

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()
app = App(token=os.environ["SLACK_BOT_TOKEN"])

CHANNEL = os.environ.get("SLACK_TEST_CHANNEL", "legal")


def channel_id(name: str) -> str:
    for page in app.client.conversations_list(types="public_channel", limit=200):
        for ch in page["channels"]:
            if ch["name"] == name:
                return ch["id"]
    raise SystemExit(f"Canalul #{name} nu exista")


def card(decision: str | None = None) -> list:
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "coLEX: lege nouă relevantă"}},
        {"type": "section", "text": {"type": "mrkdwn", "text":
            "*DORA (UE) 2022/2554, art. 30* — clauze contractuale obligatorii pentru furnizorii IT.\n"
            "• 3 contracte fără clauză de audit\n• 1 contract fără locația datelor\n"
            "_Test de integrare — date fictive PayRo._"}},
    ]
    if decision:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": decision}]})
    else:
        blocks.append({"type": "actions", "block_id": "review", "elements": [
            {"type": "button", "style": "primary", "action_id": "approve",
             "text": {"type": "plain_text", "text": "Confirm interpretarea"}, "value": "run-123"},
            {"type": "button", "style": "danger", "action_id": "reject",
             "text": {"type": "plain_text", "text": "Contest"}, "value": "run-123"},
        ]})
    return blocks


@app.action("approve")
@app.action("reject")
def on_click(ack, body, client):
    ack()                                          # Slack cere raspuns in 3 secunde
    action = body["actions"][0]["action_id"]
    user = body["user"]["id"]
    when = datetime.now().strftime("%H:%M:%S")
    verdict = "✅ Confirmat" if action == "approve" else "❌ Contestat"
    # aici coLEX ar relua rularea body["actions"][0]["value"] din checkpoint
    client.chat_update(channel=body["channel"]["id"], ts=body["message"]["ts"],
                       text=f"{verdict} de <@{user}>", blocks=card(f"{verdict} de <@{user}> la {when}"))
    print(f"[coLEX] {verdict} de {user} pentru {body['actions'][0]['value']}")


@app.command("/colex")
def on_command(ack, respond, command):
    ack()
    respond(f"coLEX este online. Ai scris: `{command.get('text') or 'status'}`")


if __name__ == "__main__":
    cid = channel_id(CHANNEL)
    app.client.chat_postMessage(channel=cid, text="coLEX: lege nouă relevantă", blocks=card())
    print(f"Card trimis in #{CHANNEL}. Astept click-uri (Ctrl+C pentru oprire)...")
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()