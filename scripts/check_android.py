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
                        # Grab a snippet around the keyword for Claude analysis
                        "snippet": _extract_snippet(content, kw),
                    }
                )
                break  # one hit per source is enough
    return detected


def _extract_snippet(content, keyword, window=300):
    """Return up to `window` chars of context around the first keyword match."""
    idx = content.find(keyword)
    if idx == -1:
        return ""
    start = max(0, idx - window // 2)
    end = min(len(content), idx + window // 2)
    return content[start:end].strip()


# ---------------------------------------------------------------------------
# Claude API analysis — optional, activated when ANTHROPIC_API_KEY is set
# ---------------------------------------------------------------------------

def analyze_with_claude(detections):
    """
    Use Claude to verify whether keyword hits are genuine X Chat Android
    launch signals or noise. Returns a filtered + enriched list.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return detections  # fall back to raw keyword results

    try:
        import anthropic
    except ImportError:
        print("anthropic package not installed — skipping Claude analysis.")
        return detections

    client = anthropic.Anthropic(api_key=api_key)

    snippets_text = "\n\n".join(
        f"[{i+1}] Source: {d['source']}\nKeyword hit: '{d['keyword']}'\nSnippet:\n{d['snippet'] or '(no snippet)'}"
        for i, d in enumerate(detections)
    )

    prompt = f"""You are monitoring for X Chat (the messaging feature inside the X/Twitter app) launching on Android.

Below are {len(detections)} keyword hit(s) from web sources. For each one, decide:
- Is this a genuine signal that X Chat is launching / has launched on Android?
- Or is it noise (unrelated Android news, old articles, generic mentions)?

Respond with a JSON array. Each element must have:
  "index": (1-based, matching the list below),
  "genuine": true or false,
  "confidence": "high" | "medium" | "low",
  "reason": one sentence

Snippets:
{snippets_text}

Respond ONLY with the JSON array, no other text."""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        verdicts = json.loads(message.content[0].text)
    except Exception as e:
        print(f"Claude analysis failed: {e} — using raw detections.")
        return detections

    # Attach Claude's verdict to each detection; filter out low-confidence noise
    enriched = []
    for v in verdicts:
        idx = v["index"] - 1
        if idx < 0 or idx >= len(detections):
            continue
        d = detections[idx].copy()
        d["claude_genuine"] = v.get("genuine", True)
        d["claude_confidence"] = v.get("confidence", "low")
        d["claude_reason"] = v.get("reason", "")
        if v.get("genuine", True):
            enriched.append(d)
        else:
            print(f"Claude filtered out '{d['source']}' ({v.get('reason', '')})")

    return enriched if enriched else detections  # never suppress everything


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
    lines = []
    for d in detections:
        line = f"• {d['source']}: '{d['keyword']}'\n  {d['url']}"
        if d.get("claude_reason"):
            line += f"\n  Claude: {d['claude_reason']} ({d.get('claude_confidence', '?')} confidence)"
        lines.append(line)
    body = "\n".join(lines)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return f"🚨 <b>X CHAT ANDROID SIGNAL DETECTED!</b>\n\n{body}\n\nDetected at: {timestamp}"


def main():
    print(f"Run started at {datetime.utcnow().isoformat()}")

    detections = check_sources()

    if not detections:
        print("No new signals.")
        return

    # Run Claude analysis if API key is present
    detections = analyze_with_claude(detections)

    if not detections:
        print("Claude filtered all detections as noise.")
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
