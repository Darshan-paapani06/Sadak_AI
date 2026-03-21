"""
SADAK AI v3 — Location API
"""
import sqlite3, os, logging

logger = logging.getLogger(__name__)
LOC_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "location.db")

def _conn():
    c = sqlite3.connect(LOC_DB)
    c.row_factory = sqlite3.Row
    return c

def get_states():
    try:
        with _conn() as db:
            rows = db.execute("SELECT name, code, type FROM states ORDER BY name").fetchall()
        return [{"name": r["name"], "code": r["code"] or "", "type": r["type"] or "STATE"} for r in rows]
    except Exception as e:
        logger.error("get_states error: %s", e)
        return []

def get_districts(state_name):
    try:
        with _conn() as db:
            sid = db.execute("SELECT id FROM states WHERE LOWER(name)=LOWER(?)", (state_name,)).fetchone()
            if not sid:
                return []
            rows = db.execute("SELECT name FROM districts WHERE state_id=? ORDER BY name", (sid["id"],)).fetchall()
        return [r["name"] for r in rows]
    except Exception as e:
        logger.error("get_districts error: %s", e)
        return []

def get_localities(state_name, district_name):
    try:
        with _conn() as db:
            sid = db.execute("SELECT id FROM states WHERE LOWER(name)=LOWER(?)", (state_name,)).fetchone()
            if not sid:
                return []
            did = db.execute("SELECT id FROM districts WHERE state_id=? AND LOWER(name)=LOWER(?)",
                             (sid["id"], district_name)).fetchone()
            if not did:
                return []
            rows = db.execute("SELECT name, type FROM localities WHERE district_id=? ORDER BY name",
                              (did["id"],)).fetchall()
        return [{"name": r["name"], "type": r["type"] or "VILLAGE"} for r in rows]
    except Exception as e:
        logger.error("get_localities error: %s", e)
        return []