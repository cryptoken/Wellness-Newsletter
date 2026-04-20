"""
Topic memory — per-practice SQLite history of newsletter runs.

Used by discover_trending_topic() to exclude recently-covered topics.
Hybrid exclusion window: last N runs OR last M days (union, so "max" window wins).
"""

import os
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = os.environ.get("RUN_HISTORY_DB", "data/run_history.db")


def _ensure_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                practice_slug TEXT NOT NULL,
                topic TEXT NOT NULL,
                discovery_method TEXT,
                mean_interest REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_runs_practice_created ON runs(practice_slug, created_at)"
        )


def slugify(name: str) -> str:
    """Practice name to slug. 'Vitality Wellness Center' -> 'vitality_wellness_center'."""
    s = (name or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "unknown"


def recent_topics(practice_slug: str, limit_runs: int = 12, limit_days: int = 90) -> list:
    """Return distinct topics covered in the last N runs OR last M days (union)."""
    _ensure_db()
    cutoff = (datetime.utcnow() - timedelta(days=limit_days)).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        by_date = conn.execute(
            "SELECT topic FROM runs WHERE practice_slug=? AND created_at >= ?",
            (practice_slug, cutoff),
        ).fetchall()
        by_count = conn.execute(
            "SELECT topic FROM runs WHERE practice_slug=? ORDER BY created_at DESC LIMIT ?",
            (practice_slug, limit_runs),
        ).fetchall()
    seen = []
    for r in list(by_date) + list(by_count):
        if r["topic"] not in seen:
            seen.append(r["topic"])
    return seen


def last_covered_at(practice_slug: str) -> dict:
    """Return {topic: latest_created_at_iso}. Used for oldest-first recycling fallback."""
    _ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT topic, MAX(created_at) AS last_seen FROM runs WHERE practice_slug=? GROUP BY topic",
            (practice_slug,),
        ).fetchall()
    return {r["topic"]: r["last_seen"] for r in rows}


def record_run(
    practice_slug: str,
    topic: str,
    discovery_method: str = "pytrends",
    mean_interest: float = 0.0,
) -> None:
    _ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO runs (practice_slug, topic, discovery_method, mean_interest) VALUES (?, ?, ?, ?)",
            (practice_slug, topic, discovery_method, float(mean_interest or 0.0)),
        )
        conn.commit()
