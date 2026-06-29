import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "data" / "osint.db"


def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS signals (
            id         TEXT PRIMARY KEY,
            source     TEXT NOT NULL,
            category   TEXT NOT NULL,
            title      TEXT,
            body       TEXT,
            url        TEXT,
            score      INTEGER DEFAULT 0,
            alerted    INTEGER DEFAULT 0,
            first_seen TEXT NOT NULL,
            last_seen  TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_score   ON signals(score);
        CREATE INDEX IF NOT EXISTS idx_alerted ON signals(alerted);
    """)
    conn.commit()
    conn.close()


def upsert_signal(signal_id, source, category, title, body, url, score):
    now = datetime.utcnow().isoformat()
    conn = get_conn()
    conn.execute("""
        INSERT INTO signals (id, source, category, title, body, url, score, alerted, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            score     = MAX(score, excluded.score),
            last_seen = excluded.last_seen
    """, (signal_id, source, category, title, body, url, score, now, now))
    conn.commit()
    conn.close()


def get_unalerted(min_score=5):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM signals WHERE alerted = 0 AND score >= ? ORDER BY score DESC",
        (min_score,)
    ).fetchall()
    conn.close()
    return rows


def mark_alerted(signal_ids):
    conn = get_conn()
    conn.executemany(
        "UPDATE signals SET alerted = 1 WHERE id = ?",
        [(sid,) for sid in signal_ids]
    )
    conn.commit()
    conn.close()
