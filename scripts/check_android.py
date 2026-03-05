import requests
import os
import json
from datetime import datetime


SOURCES = [
    {
        "name": "Michael Boswell (Nitter)",
        "url": "https://nitter.net/mb",
        "keywords": ["android", "x chat", "android version"],
    },
    {
        "name": "TechCrunch X Chat",
        "url": "https://techcrunch.com/tag/x-chat/",
        "keywords": ["android", "launch", "release"],
    },
    {
        "name": "X Newsroom",
        "url": "https://news.x.com/",
        "keywords": ["android", "mobile", "x chat"],
    },
    {
        "name": "TechCrunch X Chat RSS",
        "url": "https://techcrunch.com/tag/x-chat/feed/",
        "keywords": ["android", "launch", "release"],
    },
]


def check_x_chat_sources():
    """Check multiple sources for X Chat Android news."""
    detected = []

    for source in SOURCES:
        try:
            response = requests.get(
                source["url"],
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (compatible; XChatAndroidChecker/1.0)"},
            )
            if response.status_code == 200:
                content = response.text.lower()
                for keyword in source["keywords"]:
                    if keyword in content:
                        detected.append(
                            {
                                "source": source["name"],
                                "keyword": keyword,
                                "url": source["url"],
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                        break  # One match per source is enough
        except Exception as e:
            print(f"Error checking {source['name']}: {e}")

    return detected


def send_telegram_alert(message):
    """Send alert via Telegram bot."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not (bot_token and chat_id):
        print("Telegram credentials not configured, skipping.")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    resp = requests.post(url, json=payload, timeout=10)
    if resp.ok:
        print("Telegram alert sent.")
    else:
        print(f"Telegram alert failed: {resp.status_code} {resp.text}")


def send_slack_alert(message):
    """Send alert via Slack incoming webhook."""
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        print("Slack webhook not configured, skipping.")
        return

    resp = requests.post(webhook, json={"text": message}, timeout=10)
    if resp.ok:
        print("Slack alert sent.")
    else:
        print(f"Slack alert failed: {resp.status_code} {resp.text}")


def send_discord_alert(message):
    """Send alert via Discord webhook."""
    webhook = os.environ.get("DISCORD_WEBHOOK")
    if not webhook:
        print("Discord webhook not configured, skipping.")
        return

    # Discord uses 'content' key and has a 2000-char limit
    resp = requests.post(webhook, json={"content": message[:2000]}, timeout=10)
    if resp.ok:
        print("Discord alert sent.")
    else:
        print(f"Discord alert failed: {resp.status_code} {resp.text}")


def build_alert_message(results):
    """Build a human-readable alert message from detection results."""
    msg = "🚨 <b>X CHAT ANDROID DETECTED!</b>\n\n"
    for r in results:
        msg += f"• {r['source']}: Found '{r['keyword']}'\n  {r['url']}\n\n"
    msg += f"Detected at: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
    return msg


def main():
    print(f"Checking for X Chat Android news at {datetime.now()}")

    results = check_x_chat_sources()

    if results:
        alert = build_alert_message(results)
        print(alert)

        send_telegram_alert(alert)
        send_slack_alert(alert)
        send_discord_alert(alert)

        with open("detections.json", "w") as f:
            json.dump(results, f, indent=2)

        print(f"\nDetection saved to detections.json ({len(results)} match(es)).")
    else:
        print("No Android launch news detected this run.")


if __name__ == "__main__":
    main()
