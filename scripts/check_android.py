import requests
import os
import json
import hashlib
from datetime import datetime


SOURCES = [
    {
        "name": "TechCrunch X Chat",
        "url": "https://techcrunch.com/tag/x-chat/",
        "keywords": [
            "android",
            "google play",
            "play store",
            "beta android",
            "release android",
            "coming to android",
            "apk",
            "rollout",
        ],
    },
    {
        "name": "TechCrunch X Chat RSS",
        "url": "https://techcrunch.com/tag/x-chat/feed/",
        "keywords": ["android", "google play", "play store", "apk", "rollout"],
    },
    {
        "name": "PCMag X Chat",
        "url": "https://www.pcmag.com/search?q=x+chat",
        "keywords": ["android", "google play", "play store", "apk"],
    },
    {
        "name": "Michael Boswell (Nitter)",
        "url": "https://nitter.poast.org/mjboswell",
        "keywords": ["android", "xchat android", "x chat android", "play store", "apk"],
    },
    {
        "name": "X Engineering (Nitter)",
        "url": "https://nitter.poast.org/XEng",
        "keywords": ["x chat", "android", "play store"],
    },
    {
        "name": "Play Store X Chat search",
        "url": "https://play.google.com/store/search?q=x+chat&c=apps",
        "keywords": ["x chat", "x corp", "twitter", "com.x.chat"],
    },
]


def get_content(url):
    try:
        resp = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "XChatAndroidChecker/1.0"},
        )
        resp.raise_for_status()
        return resp.text.lower()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""


def check_sources():
    """Scan all sources and return a list of keyword hits."""
    detected = []
    for src in SOURCES:
        content = get_content(src["url"])
        if not content:
            continue
        for kw in src["keywords"]:
            if kw in content:
                detected.append(
                    {
                        "source": src["name"],
                        "keyword": kw,
                        "url": src["url"],
                        "time": datetime.utcnow().isoformat(),
                    }
                )
                break  # one hit per source is enough
    return detected


def load_last_hash():
    try:
        with open("last_alert_hash.txt") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def save_last_hash(hash_val):
    with open("last_alert_hash.txt", "w") as f:
        f.write(hash_val)


def send_telegram(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        print("Telegram not configured, skipping.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
        timeout=10,
    )
    print("Telegram sent." if resp.ok else f"Telegram failed: {resp.status_code} {resp.text}")


def send_slack(message):
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        print("Slack not configured, skipping.")
        return
    resp = requests.post(webhook, json={"text": message}, timeout=10)
    print("Slack sent." if resp.ok else f"Slack failed: {resp.status_code} {resp.text}")


def send_discord(message):
    webhook = os.environ.get("DISCORD_WEBHOOK")
    if not webhook:
        print("Discord not configured, skipping.")
        return
    resp = requests.post(webhook, json={"content": message[:2000]}, timeout=10)
    print("Discord sent." if resp.ok else f"Discord failed: {resp.status_code} {resp.text}")


def build_message(detections):
    lines = "\n".join(
        f"• {d['source']}: '{d['keyword']}'\n  {d['url']}" for d in detections
    )
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return f"🚨 <b>X CHAT ANDROID SIGNAL DETECTED!</b>\n\n{lines}\n\nDetected at: {timestamp}"


def main():
    print(f"Run started at {datetime.utcnow().isoformat()}")

    detections = check_sources()

    if not detections:
        print("No new signals.")
        return

    # Deduplicate: skip alert if the exact same set of hits was already reported
    det_hash = hashlib.md5(
        json.dumps(detections, sort_keys=True).encode()
    ).hexdigest()

    if det_hash == load_last_hash():
        print("Same detections as last run — skipping duplicate alert.")
        return

    message = build_message(detections)
    print(message)

    send_telegram(message)
    send_slack(message)
    send_discord(message)

    save_last_hash(det_hash)

    with open("detections.json", "w") as f:
        json.dump(detections, f, indent=2)

    print(f"\n{len(detections)} detection(s) saved to detections.json.")


if __name__ == "__main__":
    main()
