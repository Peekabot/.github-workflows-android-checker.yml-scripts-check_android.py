"""
generate_prompts.py — Generate a sellable prompt pack for a given topic.

Usage:
    python scripts/generate_prompts.py "LinkedIn Thought Leadership"

Writes two files under products/<topic>/:
    prompts.json   — machine-readable pack
    README.md      — human-readable preview / product description
"""

import os
import sys
import json
import re
import requests
from datetime import datetime
from pathlib import Path

NICHE = os.getenv("NICHE", "business").lower().strip()

SYSTEM_PROMPTS = {
    "business": (
        "You are an expert business consultant and prompt engineer. "
        "Create prompts that help founders, marketers, and sales teams get "
        "measurable results fast."
    ),
    "coding": (
        "You are a senior software engineer and prompt engineer. "
        "Create prompts that help developers write better code, debug faster, "
        "and level up their technical skills."
    ),
    "creative": (
        "You are a professional copywriter and creative director. "
        "Create prompts that help content creators produce compelling, "
        "high-converting material across formats."
    ),
    "productivity": (
        "You are a productivity coach and systems thinker. "
        "Create prompts that help people build better habits, manage their "
        "time, and accomplish more of what matters."
    ),
}

PROMPT_COUNT = 10
PRICE_CENTS = 1900  # $19.00


def system_prompt():
    return SYSTEM_PROMPTS.get(NICHE, SYSTEM_PROMPTS["business"])


def generate_via_openai(topic: str) -> list[dict]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    user_msg = f"""Create {PROMPT_COUNT} high-quality, immediately usable AI prompts about "{topic}".

Return ONLY a valid JSON array. Each element must have exactly these keys:
  "title"       – 4-8 word name for the prompt
  "prompt"      – the full prompt text (50-150 words), ready to paste into ChatGPT/Claude
  "description" – one sentence explaining when/why to use it

No markdown fences, no explanation outside the JSON array."""

    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.8,
        "response_format": {"type": "json_object"},
    }

    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()

    raw = resp.json()["choices"][0]["message"]["content"]

    # gpt-4o with json_object wraps in an object; unwrap if needed
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        # look for the list value
        for v in parsed.values():
            if isinstance(v, list):
                return v
        raise ValueError(f"Unexpected JSON shape: {list(parsed.keys())}")
    return parsed


def make_slug(topic: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", topic)
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug


def write_outputs(topic: str, prompts: list[dict]) -> Path:
    slug = make_slug(topic)
    out_dir = Path("products") / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = out_dir / "prompts.json"
    json_path.write_text(json.dumps(prompts, indent=2))

    # Markdown product description (also useful as Gumroad description)
    lines = [
        f"# {topic} — AI Prompt Pack",
        f"",
        f"**{len(prompts)} ready-to-use prompts** — paste straight into ChatGPT, Claude, or any AI assistant.",
        f"",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d')}",
        f"",
        f"---",
        f"",
    ]
    for i, p in enumerate(prompts, 1):
        lines += [
            f"## {i}. {p['title']}",
            f"",
            f"**When to use:** {p['description']}",
            f"",
            f"```",
            p["prompt"],
            f"```",
            f"",
        ]

    readme_path = out_dir / "README.md"
    readme_path.write_text("\n".join(lines))

    return out_dir


def main():
    topic = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else "AI Productivity"
    print(f"Generating prompt pack for: {topic}", file=sys.stderr)

    try:
        prompts = generate_via_openai(topic)
    except Exception as e:
        print(f"OpenAI generation failed: {e}", file=sys.stderr)
        # Structured fallback so the pipeline never hard-fails
        prompts = [
            {
                "title": f"Expert {topic} Advisor",
                "prompt": (
                    f"You are a world-class expert in {topic}. "
                    "I will describe my situation and you will provide specific, "
                    "actionable advice tailored to my context. "
                    "Ask clarifying questions if needed before giving recommendations."
                ),
                "description": f"Use when you need strategic advice on {topic}.",
            }
        ]

    out_dir = write_outputs(topic, prompts)
    print(f"Wrote {len(prompts)} prompts to {out_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
