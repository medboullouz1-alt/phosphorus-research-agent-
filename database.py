"""
Database layer — SQLite archive stored inside the GitHub repository.
"""
import sqlite3, csv, json, logging
from pathlib import Path
import config

logger = logging.getLogger(__name__)

def get_conn():
    Path(config.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS papers (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            doi            TEXT    UNIQUE,
            title          TEXT    NOT NULL,
            authors        TEXT,
            journal        TEXT,
            year           INTEGER,
            abstract       TEXT,
            url            TEXT,
            citation_count INTEGER DEFAULT 0,
            theme          TEXT,
            date_processed TEXT    DEFAULT (datetime('now')),
            full_summary   TEXT,
            keywords       TEXT,
            study_region   TEXT,
            methodology    TEXT,
            key_findings   TEXT,
            ghg_result     TEXT,
            implications   TEXT,
            limitations    TEXT
        );
        CREATE TABLE IF NOT EXISTS daily_digests (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            date             TEXT    UNIQUE,
            theme            TEXT,
            paper_ids        TEXT,
            synthesis        TEXT,
            key_takeaway     TEXT,
            emerging_pattern TEXT,
            research_gap     TEXT,
            practical_impl   TEXT,
            telegram_sent    INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_doi  ON papers(doi);
        CREATE INDEX IF NOT EXISTS idx_year ON papers(year);
        """)
    logger.info("Database ready.")

def save_paper(p):
    fields = [
        "doi", "title", "authors", "journal", "year", "abstract", "url",
        "citation_count", "theme", "full_summary", "keywords",
        "study_region", "methodology", "key_findings", "ghg_result",
        "implications", "limitations"
    ]
    data = {f: p.get(f) for f in fields}
    cols = ", ".join(data)
    ph   = ", ".join(["?"] * len(data))
    upd  = ", ".join([f"{k}=excluded.{k}" for k in data])
    with get_conn() as conn:
        cur = conn.execute(
            f"INSERT INTO papers ({cols}) VALUES ({ph}) "
            f"ON CONFLICT(doi) DO UPDATE SET {upd}",
            list(data.values()))
        return cur.lastrowid

def save_digest(d):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO daily_digests
               (date, theme, paper_ids, synthesis, key_takeaway,
                emerging_pattern, research_gap, practical_impl, telegram_sent)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (d["date"], d["theme"], json.dumps(d.get("paper_ids", [])),
             d.get("synthesis"), d.get("key_takeaway"), d.get("emerging_pattern"),
             d.get("research_gap"), d.get("practical_impl"),
             int(d.get("telegram_sent", False))))

def get_seen_dois(days=90):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT doi FROM papers WHERE doi IS NOT NULL "
            "AND date_processed >= datetime('now', ?)",
            (f"-{days} days",)).fetchall()
    return {r["doi"] for r in rows}

def export_csv(path="data/papers_database.csv"):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM papers ORDER BY year DESC").fetchall()
    if not rows:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows([dict(r) for r in rows])
    logger.info("CSV exported: %s", path)
