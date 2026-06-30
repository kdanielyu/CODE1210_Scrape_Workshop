import io
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .models import Place, Review, SearchJob, SocialPost

DB_PATH = Path(__file__).parent.parent / "data" / "urban_data.db"


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db() -> None:
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id           TEXT PRIMARY KEY,
            location     TEXT,
            latitude     REAL,
            longitude    REAL,
            radius_m     INTEGER,
            sources      TEXT,
            status       TEXT,
            created_at   TEXT,
            completed_at TEXT,
            record_count INTEGER DEFAULT 0,
            error        TEXT,
            place_types  TEXT,
            min_results  INTEGER DEFAULT 0,
            max_results  INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS places (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id       TEXT,
            source       TEXT,
            place_id     TEXT,
            name         TEXT,
            address      TEXT,
            latitude     REAL,
            longitude    REAL,
            rating       REAL,
            review_count INTEGER,
            categories   TEXT,
            price_level  INTEGER,
            phone        TEXT,
            url          TEXT,
            fetched_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id          TEXT,
            source          TEXT,
            place_id        TEXT,
            place_name      TEXT,
            author          TEXT,
            rating          REAL,
            text            TEXT,
            sentiment_score REAL,
            sentiment_label TEXT,
            published_at    TEXT,
            fetched_at      TEXT
        );

        CREATE TABLE IF NOT EXISTS social_posts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id          TEXT,
            source          TEXT,
            post_id         TEXT,
            subreddit       TEXT,
            title           TEXT,
            body            TEXT,
            author          TEXT,
            score           INTEGER,
            comment_count   INTEGER,
            url             TEXT,
            latitude        REAL,
            longitude       REAL,
            sentiment_score REAL,
            sentiment_label TEXT,
            published_at    TEXT,
            fetched_at      TEXT
        );
    """)
    # Migrate older databases that predate the scrape-settings columns.
    existing = {r[1] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    for col, ddl in (("place_types", "TEXT"),
                     ("min_results", "INTEGER DEFAULT 0"),
                     ("max_results", "INTEGER DEFAULT 0")):
        if col not in existing:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {ddl}")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Job helpers
# ---------------------------------------------------------------------------

def upsert_job(job: SearchJob) -> None:
    conn = _connect()
    conn.execute(
        """
        INSERT OR REPLACE INTO jobs
            (id, location, latitude, longitude, radius_m, sources,
             status, created_at, completed_at, record_count, error,
             place_types, min_results, max_results)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job.id, job.location, job.latitude, job.longitude,
            job.radius_m, job.sources, job.status,
            job.created_at, job.completed_at, job.record_count, job.error,
            job.place_types, job.min_results, job.max_results,
        ),
    )
    conn.commit()
    conn.close()


def update_job_status(
    job_id: str,
    status: str,
    record_count: Optional[int] = None,
    completed_at: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    parts = ["status = ?"]
    params: list = [status]
    if record_count is not None:
        parts.append("record_count = ?")
        params.append(record_count)
    if completed_at is not None:
        parts.append("completed_at = ?")
        params.append(completed_at)
    if error is not None:
        parts.append("error = ?")
        params.append(error)
    params.append(job_id)

    conn = _connect()
    conn.execute(f"UPDATE jobs SET {', '.join(parts)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def get_job(job_id: str) -> Optional[Dict]:
    conn = _connect()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_jobs() -> List[Dict]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_job(job_id: str) -> None:
    """Permanently delete a job and all its associated records."""
    conn = _connect()
    for table in ("places", "reviews", "social_posts"):
        conn.execute(f"DELETE FROM {table} WHERE job_id = ?", (job_id,))
    conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()


def delete_records(table: str, row_ids: list) -> None:
    """Delete individual rows by primary-key id from places, reviews, or social_posts."""
    _VALID = {"places", "reviews", "social_posts"}
    if not row_ids or table not in _VALID:
        return
    conn = _connect()
    placeholders = ",".join("?" * len(row_ids))
    conn.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", list(row_ids))
    conn.commit()
    conn.close()


def count_records(job_id: str) -> int:
    conn = _connect()
    p = conn.execute("SELECT COUNT(*) FROM places WHERE job_id = ?", (job_id,)).fetchone()[0]
    r = conn.execute("SELECT COUNT(*) FROM reviews WHERE job_id = ?", (job_id,)).fetchone()[0]
    s = conn.execute("SELECT COUNT(*) FROM social_posts WHERE job_id = ?", (job_id,)).fetchone()[0]
    conn.close()
    return p + r + s


# ---------------------------------------------------------------------------
# Insert helpers
# ---------------------------------------------------------------------------

def insert_place(place: Place) -> None:
    conn = _connect()
    conn.execute(
        """
        INSERT INTO places
            (job_id, source, place_id, name, address, latitude, longitude,
             rating, review_count, categories, price_level, phone, url, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            place.job_id, place.source, place.place_id, place.name,
            place.address, place.latitude, place.longitude,
            place.rating, place.review_count, place.categories,
            place.price_level, place.phone, place.url, place.fetched_at,
        ),
    )
    conn.commit()
    conn.close()


def insert_review(review: Review) -> None:
    conn = _connect()
    conn.execute(
        """
        INSERT INTO reviews
            (job_id, source, place_id, place_name, author, rating, text,
             sentiment_score, sentiment_label, published_at, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            review.job_id, review.source, review.place_id, review.place_name,
            review.author, review.rating, review.text,
            review.sentiment_score, review.sentiment_label,
            review.published_at, review.fetched_at,
        ),
    )
    conn.commit()
    conn.close()


def insert_social_post(post: SocialPost) -> None:
    conn = _connect()
    conn.execute(
        """
        INSERT INTO social_posts
            (job_id, source, post_id, subreddit, title, body, author,
             score, comment_count, url, latitude, longitude,
             sentiment_score, sentiment_label, published_at, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            post.job_id, post.source, post.post_id, post.subreddit,
            post.title, post.body, post.author,
            post.score, post.comment_count, post.url,
            post.latitude, post.longitude,
            post.sentiment_score, post.sentiment_label,
            post.published_at, post.fetched_at,
        ),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Query helpers (return DataFrames)
# ---------------------------------------------------------------------------

def _query_df(table: str, job_id: Optional[str], source: Optional[str]) -> pd.DataFrame:
    conn = _connect()
    sql = f"SELECT * FROM {table} WHERE 1=1"
    params: list = []
    if job_id:
        sql += " AND job_id = ?"
        params.append(job_id)
    if source:
        sql += " AND source = ?"
        params.append(source)
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def get_places_df(job_id: Optional[str] = None, source: Optional[str] = None) -> pd.DataFrame:
    return _query_df("places", job_id, source)


def get_reviews_df(job_id: Optional[str] = None, source: Optional[str] = None) -> pd.DataFrame:
    return _query_df("reviews", job_id, source)


def get_social_posts_df(job_id: Optional[str] = None, source: Optional[str] = None) -> pd.DataFrame:
    return _query_df("social_posts", job_id, source)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_to_bytes(job_id: str, fmt: str) -> bytes:
    sheets = {
        "places":       get_places_df(job_id),
        "reviews":      get_reviews_df(job_id),
        "social_posts": get_social_posts_df(job_id),
    }

    if fmt == "csv":
        frames = []
        for name, df in sheets.items():
            if not df.empty:
                df = df.copy()
                df.insert(0, "_table", name)
                frames.append(df)
        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        return combined.to_csv(index=False).encode("utf-8")

    if fmt == "xlsx":
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            for name, df in sheets.items():
                if not df.empty:
                    df.to_excel(writer, sheet_name=name, index=False)
        return buf.getvalue()

    if fmt == "json":
        payload = {k: v.to_dict(orient="records") for k, v in sheets.items()}
        return json.dumps(payload, indent=2, default=str).encode("utf-8")

    return b""
