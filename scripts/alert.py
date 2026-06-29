"""
Sends opportunity alerts via Telegram and Discord.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from store import mark_alerted
from cross_reference import build_opportunities, ALERT_THRESHOLD

CONFIG = json.loads((Path(__file__).parent.parent / "config.json").read_text())


def _send_telegram(message: str) -> bool:
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        print("Telegram not configured.")
        return False
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=10,
    )
    return resp.ok


def _send_discord(message: str) -> bool:
    webhook = os.getenv("DISCORD_WEBHOOK")
    if not webhook:
        print("Discord not configured.")
        return False
    plain = (message
             .replace("<b>", "**").replace("</b>", "**")
             .replace("<i>", "_").replace("</i>", "_"))
    resp = requests.post(webhook, json={"content": plain[:2000]}, timeout=10)
    return resp.ok


def _format(opp: dict) -> str:
    tag   = "DEMAND" if opp["category"] == "demand" else "TALENT"
    lines = [f"<b>[{tag} | score:{opp['score']}]</b> {opp['title'] or 'Untitled'}",
             f"<i>{opp['source']}</i>"]
    if opp.get("url"):
        lines.append(opp["url"])
    if opp.get("talent_matches"):
        lines.append("Possible talent: " + ", ".join(t["title"][:40] for t in opp["talent_matches"]))
    return "\n".join(lines)


def run_alerts():
    opportunities = build_opportunities(threshold=ALERT_THRESHOLD)
    if not opportunities:
        print(f"No opportunities above alert threshold ({ALERT_THRESHOLD}).")
        return

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    parts = [f"<b>Capital Region OSINT — {len(opportunities)} signal(s)</b>\n{timestamp}"]
    parts += [_format(o) for o in opportunities[:10]]
    message = "\n\n".join(parts)

    sent = False
    if CONFIG["notifications"].get("telegram"):
        ok = _send_telegram(message)
        print(f"Telegram: {'sent' if ok else 'failed'}")
        sent = sent or ok
    if CONFIG["notifications"].get("discord"):
        ok = _send_discord(message)
        print(f"Discord: {'sent' if ok else 'failed'}")
        sent = sent or ok

    if sent:
        mark_alerted([o["id"] for o in opportunities])


if __name__ == "__main__":
    run_alerts()
