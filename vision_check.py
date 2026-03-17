"""
vision_check.py — Gemini-powered health diagnostics for OpenPantry assets.

Usage (standalone):
    GEMINI_API_KEY=... ASSET_TYPE=yeast python vision_check.py
    GEMINI_API_KEY=... ASSET_TYPE=herb  python vision_check.py

Or import and call diagnose(asset_type, **kwargs) from other scripts.
"""

import os
from datetime import date, datetime

import google.generativeai as genai


# ── Setup ─────────────────────────────────────────────────────────────────────

def _client():
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    return genai.GenerativeModel("gemini-1.5-flash")


# ── Season helper ─────────────────────────────────────────────────────────────

def current_season():
    month = date.today().month
    if month in (3, 4, 5):   return "Spring"
    if month in (6, 7, 8):   return "Summer"
    if month in (9, 10, 11): return "Autumn"
    return "Winter"


# ── Yeast prompt ──────────────────────────────────────────────────────────────

def build_yeast_prompt(
    name,
    last_feed,           # ISO date string
    storage="counter",   # "counter" or "fridge"
    appearance="bubbly",
    smell="sweet/alcoholic",
    rise_hours=None,
):
    hours_since = ""
    if last_feed:
        delta = datetime.now() - datetime.fromisoformat(last_feed)
        hours_since = f"{int(delta.total_seconds() // 3600)}h ago"

    return f"""
Sourdough starter "{name}":
- Last fed: {last_feed} ({hours_since})
- Storage: {storage}
- Appearance: {appearance}
- Smell: {smell}
- Last observed rise time: {rise_hours or "unknown"}h

Diagnose:
1. Health score (0-100%)
2. Feed now? (yes / no / optional) — explain briefly
3. Expected rise time after next feed
4. One recipe idea using discard right now
5. Mood emoji: 🍞 (thriving) / 😰 (stressed) / 💀 (critical)

Be concise. One sentence per point.
""".strip()


# ── Herb / bonsai prompt ──────────────────────────────────────────────────────

def build_herb_prompt(
    name,
    species,             # "Rosemary", "Lavender", "Thyme", etc.
    last_scan,           # ISO date string
    prev_health=None,    # int 0-100
    user_observation="",
):
    days_since = ""
    if last_scan:
        delta = date.today() - date.fromisoformat(last_scan)
        days_since = str(delta.days)

    return f"""
Herb bonsai "{name}":
- Species: {species}
- Last scan: {last_scan} ({days_since}d ago)
- Season: {current_season()}
- Previous health score: {prev_health if prev_health is not None else "unknown"}%
- User observation: {user_observation or "none"}

Diagnose:
1. Health score (0-100%)
2. Water needed? (yes / no / caution) — one-line reason
3. Prune recommendation (trim / skip / shape)
4. One care tip from bonsai practice
5. Mood emoji: 🌟 (thriving) / 👋 (needs attention) / ☁️ (struggling) / 🥀 (critical)

Be concise. One sentence per point.
""".strip()


# ── Router ────────────────────────────────────────────────────────────────────

def diagnose(asset_type, **kwargs):
    """
    asset_type: "yeast" | "herb"
    kwargs: forwarded to the appropriate prompt builder.
    Returns the raw Gemini response text.
    """
    model = _client()

    if asset_type == "yeast":
        prompt = build_yeast_prompt(**kwargs)
    elif asset_type == "herb":
        prompt = build_herb_prompt(**kwargs)
    else:
        raise ValueError(f"Unknown asset_type '{asset_type}'. Use 'yeast' or 'herb'.")

    response = model.generate_content(prompt)
    return response.text


# ── CLI demo ──────────────────────────────────────────────────────────────────

def main():
    asset_type = os.getenv("ASSET_TYPE", "herb").lower()

    if asset_type == "yeast":
        result = diagnose(
            "yeast",
            name=os.getenv("ASSET_NAME", "Bread Pitt"),
            last_feed=os.getenv("LAST_EVENT", date.today().isoformat()),
            storage=os.getenv("STORAGE", "counter"),
            appearance=os.getenv("APPEARANCE", "bubbly, doubled in size"),
            smell=os.getenv("SMELL", "sweet and slightly alcoholic"),
        )
    else:
        result = diagnose(
            "herb",
            name=os.getenv("ASSET_NAME", "Rosie"),
            species=os.getenv("SPECIES", "Rosemary"),
            last_scan=os.getenv("LAST_EVENT", date.today().isoformat()),
            prev_health=int(os.getenv("PREV_HEALTH", "98")),
            user_observation=os.getenv("OBSERVATION", ""),
        )

    print(result)


if __name__ == "__main__":
    main()
