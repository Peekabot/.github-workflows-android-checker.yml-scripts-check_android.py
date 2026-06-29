"""
Pairs demand signals with available talent signals from the same service category.
Returns ranked opportunity objects ready to alert on.
"""

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from store import get_conn

CONFIG = json.loads((Path(__file__).parent.parent / "config.json").read_text())
MIN_SCORE      = CONFIG["scoring"]["min_score"]
ALERT_THRESHOLD = CONFIG["scoring"]["alert_threshold"]


def _find_talent(demand_title: str) -> list:
    keywords = [w for w in demand_title.lower().split() if len(w) >= 4]
    conn = get_conn()
    seen, talent = set(), []
    for kw in keywords:
        rows = conn.execute("""
            SELECT * FROM signals
            WHERE category = 'supply' AND (title LIKE ? OR body LIKE ?)
            LIMIT 3
        """, (f"%{kw}%", f"%{kw}%")).fetchall()
        for r in rows:
            if r["id"] not in seen:
                seen.add(r["id"])
                talent.append(dict(r))
    conn.close()
    return talent[:3]


def build_opportunities(threshold=None) -> list:
    threshold = threshold if threshold is not None else MIN_SCORE
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM signals
        WHERE alerted = 0 AND score >= ?
        ORDER BY score DESC, first_seen DESC
        LIMIT 50
    """, (threshold,)).fetchall()
    conn.close()

    opportunities = []
    for row in rows:
        opp = dict(row)
        opp["talent_matches"] = _find_talent(row["title"] or "") if row["category"] == "demand" else []
        opportunities.append(opp)

    return opportunities


if __name__ == "__main__":
    opps = build_opportunities()
    print(f"Opportunities above threshold: {len(opps)}")
    for o in opps[:5]:
        print(f"\n  [{o['score']}] {o['title']}")
        print(f"  {o['source']} — {o['url']}")
        if o["talent_matches"]:
            print(f"  Talent: {', '.join(t['title'][:50] for t in o['talent_matches'])}")
