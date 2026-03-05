"""
find_trend.py — Discover a trending topic worth packaging as a prompt pack.

Priority order:
  1. Perplexity API  (real-time web awareness)
  2. OpenAI GPT-4o   (strong general knowledge fallback)
  3. Hard-coded list  (deterministic last resort)

The NICHE env var (set as a GitHub Actions variable) focuses the search.
Supported values: business, coding, creative, productivity (default: business)
"""

import os
import sys
import json
import random
import anthropic
from datetime import datetime

NICHE = os.getenv("NICHE", "business").lower().strip()

NICHE_DESCRIPTIONS = {
    "business": "business, marketing, sales, entrepreneurship, or B2B SaaS",
    "coding": "software engineering, DevOps, AI tooling, or developer productivity",
    "creative": "copywriting, content creation, storytelling, or visual design",
    "productivity": "personal productivity, time management, habits, or life optimization",
}

NICHE_FALLBACKS = {
    "business": [
        "Cold Email Sequences",
        "LinkedIn Thought Leadership",
        "AI Sales Automation",
        "SaaS Pricing Strategy",
        "Startup Pitch Decks",
    ],
    "coding": [
        "AI Code Review",
        "System Design Interviews",
        "DevOps Automation",
        "API Documentation",
        "Test-Driven Development",
    ],
    "creative": [
        "Long-Form Content Repurposing",
        "YouTube Script Writing",
        "Brand Voice Guidelines",
        "Newsletter Growth",
        "Short-Form Video Scripts",
    ],
    "productivity": [
        "Weekly Review Systems",
        "Second Brain Setup",
        "Deep Work Scheduling",
        "Meeting Efficiency",
        "Goal Setting Frameworks",
    ],
}


def niche_description():
    return NICHE_DESCRIPTIONS.get(NICHE, NICHE_DESCRIPTIONS["business"])


def ask_perplexity():
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        return None

    week = datetime.utcnow().strftime("week %W of %Y")
    payload = {
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": (
                    f"You are a trend analyst specialising in {niche_description()}. "
                    "Reply with ONLY a 2-4 word topic name, no explanation."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"What is the single most discussed topic in {niche_description()} "
                    f"during {week}? Return just the topic name."
                ),
            },
        ],
    }

    try:
        resp = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip().strip('"')
    except Exception as e:
        print(f"Perplexity error: {e}", file=sys.stderr)
        return None


def ask_claude():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    month = datetime.utcnow().strftime("%B %Y")

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=64,
            system=(
                f"You are a trend analyst specialising in {niche_description()}. "
                "Reply with ONLY a 2-4 word topic name, no explanation."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"What is one high-interest topic in {niche_description()} "
                    f"that people are actively searching for in {month}? "
                    "Return just the topic name."
                ),
            }],
        )
        return response.content[0].text.strip().strip('"')
    except Exception as e:
        print(f"Claude error: {e}", file=sys.stderr)
        return None


def pick_fallback():
    options = NICHE_FALLBACKS.get(NICHE, NICHE_FALLBACKS["business"])
    return options[0]


def main():
    topic = ask_perplexity() or ask_claude() or pick_fallback()
    # Sanitise for use as a folder name in the workflow
    topic = topic.replace("/", "-").replace("\\", "-")
    print(topic)


if __name__ == "__main__":
    main()
