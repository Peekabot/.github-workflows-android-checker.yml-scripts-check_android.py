"""
deploy_to_gumroad.py — Publish a generated prompt pack to Gumroad.

Usage:
    python scripts/deploy_to_gumroad.py "LinkedIn Thought Leadership"

Reads products/<slug>/prompts.json and products/<slug>/README.md,
creates a new Gumroad product, then writes products/<slug>/gumroad.json
with the product URL and ID for future reference.

Requires secret: GUMROAD_ACCESS_TOKEN
Optional override: PRICE_CENTS env var (default 1900 = $19.00)
"""

import os
import sys
import json
import re
from pathlib import Path

import requests


GUMROAD_API = "https://api.gumroad.com/v2/products"
DEFAULT_PRICE_CENTS = int(os.getenv("PRICE_CENTS", "1900"))


def make_slug(topic: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", topic)
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug


def build_description(topic: str, prompts: list[dict]) -> str:
    lines = [
        f"<h2>{topic} — AI Prompt Pack</h2>",
        f"<p><strong>{len(prompts)} ready-to-use prompts</strong> you can paste straight into "
        "ChatGPT, Claude, or any AI assistant. No fluff—every prompt is immediately actionable.</p>",
        "<h3>What's inside:</h3>",
        "<ul>",
    ]
    for p in prompts:
        lines.append(f"  <li><strong>{p['title']}</strong> — {p['description']}</li>")
    lines += [
        "</ul>",
        "<p>Download includes a clean PDF and a plain-text file for easy copy-paste.</p>",
    ]
    return "\n".join(lines)


def deploy(topic: str, token: str) -> dict:
    slug = make_slug(topic)
    product_dir = Path("products") / slug

    prompts_path = product_dir / "prompts.json"
    if not prompts_path.exists():
        raise FileNotFoundError(f"No prompts.json found at {prompts_path}. Run generate_prompts.py first.")

    prompts = json.loads(prompts_path.read_text())
    description = build_description(topic, prompts)

    data = {
        "access_token": token,
        "name": f"{topic} — AI Prompt Pack",
        "description": description,
        "price": DEFAULT_PRICE_CENTS,
        "currency": "usd",
        "require_shipping": "false",
        "published": "true",
        "tags[]": ["ai", "prompts", "productivity"],
    }

    resp = requests.post(GUMROAD_API, data=data, timeout=30)

    if not resp.ok:
        raise RuntimeError(f"Gumroad API error {resp.status_code}: {resp.text}")

    product = resp.json().get("product", {})
    result = {
        "id": product.get("id"),
        "name": product.get("name"),
        "url": product.get("short_url") or product.get("url"),
        "price_cents": DEFAULT_PRICE_CENTS,
        "topic": topic,
    }

    # Persist so the commit step captures it
    out_path = product_dir / "gumroad.json"
    out_path.write_text(json.dumps(result, indent=2))

    return result


def main():
    token = os.getenv("GUMROAD_ACCESS_TOKEN")
    if not token:
        print("GUMROAD_ACCESS_TOKEN not set — skipping Gumroad deployment.")
        return

    topic = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else "AI Productivity"

    try:
        result = deploy(topic, token)
        print(f"Deployed: {result['name']}")
        print(f"URL: {result['url']}")
    except Exception as e:
        print(f"Gumroad deployment failed: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
