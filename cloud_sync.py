"""
SADAK AI v3 — Supabase Cloud Sync
====================================
Syncs local SQLite data to Supabase PostgreSQL in background.
SQLite keeps working 100% — this is purely additive.

Setup (one time):
  pip install supabase
  Set SUPABASE_URL and SUPABASE_KEY in .env or environment variables

Supabase free tier: 500MB DB · Unlimited API calls · Real-time dashboard
"""

import os, threading, logging, json
from datetime import datetime, timezone

logger = logging.getLogger("cloud_sync")

# ── LOAD .env FILE AUTOMATICALLY ───────────────────────────────────────
try:
    from dotenv import load_dotenv
    # Find .env in the same folder as this file
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(_env_path)
except ImportError:
    pass

# ── CONFIG ─────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()

_client = None
_enabled = False


def _init():
    """Lazy init — only loads Supabase if credentials are set."""
    global _client, _enabled
    if _enabled:
        return True
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    try:
        from supabase import create_client
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        _enabled = True
        logger.info("☁️  Supabase cloud sync ACTIVE → %s", SUPABASE_URL)
        return True
    except ImportError:
        logger.warning("⚠️  supabase package not installed. Run: pip install supabase")
        return False
    except Exception as e:
        logger.error("☁️  Supabase init failed: %s", e)
        return False


def _run_async(fn, *args, **kwargs):
    """Fire-and-forget — never blocks the main request."""
    def _target():
        try:
            fn(*args, **kwargs)
        except Exception as e:
            logger.error("☁️  Cloud sync error in %s: %s", fn.__name__, e)
    t = threading.Thread(target=_target, daemon=True)
    t.start()


# ══════════════════════════════════════════════
#  PUBLIC SYNC FUNCTIONS — called from app.py
# ══════════════════════════════════════════════

def sync_complaint_filed(complaint: dict):
    """Called when a new complaint is filed."""
    _run_async(_upsert_complaint, complaint)


def sync_complaint_updated(complaint: dict):
    """Called when admin updates complaint status."""
    _run_async(_upsert_complaint, complaint)


def sync_user_created(user: dict):
    """Called when a new user registers."""
    _run_async(_upsert_user, user)


def sync_user_deleted(user_id: int):
    """Called when admin deletes a user."""
    _run_async(_delete_user, user_id)


def sync_user_updated(user: dict):
    """Called when user profile or role changes."""
    _run_async(_upsert_user, user)


def sync_full_snapshot():
    """
    Full data sync — call once on startup to push all local data to cloud.
    Run manually: python -c "from cloud_sync import sync_full_snapshot; sync_full_snapshot()"
    """
    if not _init():
        print("❌ Supabase not configured. Set SUPABASE_URL and SUPABASE_KEY first.")
        return

    print("☁️  Starting full sync to Supabase...")

    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from database import get_db, get_all_users, get_complaints

        # Sync all users
        users = get_all_users()
        for u in users:
            _upsert_user(u)
        print(f"  ✅ Synced {len(users)} users")

        # Sync all complaints
        complaints = get_complaints({"limit": 10000})
        for c in complaints:
            _upsert_complaint(dict(c))
        print(f"  ✅ Synced {len(complaints)} complaints")

        print("☁️  Full sync complete!")

    except Exception as e:
        print(f"❌ Full sync failed: {e}")


# ══════════════════════════════════════════════
#  INTERNAL SYNC WORKERS
# ══════════════════════════════════════════════

def _upsert_complaint(c: dict):
    if not _init(): return
    try:
        row = {
            "complaint_id":      c.get("complaint_id"),
            "status":            c.get("status"),
            "severity":          c.get("severity"),
            "state":             c.get("state"),
            "district":          c.get("district"),
            "description":       c.get("description"),
            "authority_name":    c.get("authority_name"),
            "authority_type":    c.get("authority_type"),
            "helpline":          str(c.get("helpline", "")),
            "latitude":          c.get("latitude"),
            "longitude":         c.get("longitude"),
            "ai_detected":       bool(c.get("ai_detected")),
            "ai_confidence":     c.get("ai_confidence"),
            "ai_pothole_count":  c.get("ai_pothole_count", 0),
            "response_deadline": c.get("response_deadline"),
            "resolved_at":       c.get("resolved_at"),
            "resolution_note":   c.get("resolution_note"),
            "user_id":           c.get("user_id"),
            "user_name":         c.get("user_name", ""),
            "filed_at":          c.get("filed_at"),
            "updated_at":        c.get("updated_at") or datetime.now(timezone.utc).isoformat(),
        }
        # Remove None values for cleaner upsert
        row = {k: v for k, v in row.items() if v is not None}
        _client.table("complaints").upsert(row, on_conflict="complaint_id").execute()
        logger.debug("☁️  Synced complaint %s", c.get("complaint_id"))
    except Exception as e:
        logger.error("☁️  _upsert_complaint failed: %s", e)


def _upsert_user(u: dict):
    if not _init(): return
    try:
        row = {
            "id":               u.get("id"),
            "full_name":        u.get("full_name"),
            "email":            u.get("email"),
            "state":            u.get("state", ""),
            "district":         u.get("district", ""),
            "role":             u.get("role", "citizen"),
            "is_active":        bool(u.get("is_active", 1)),
            "complaints_count": u.get("complaints_count", 0),
            "avatar_color":     u.get("avatar_color", "#0EA5E9"),
            "created_at":       u.get("created_at"),
            "last_login":       u.get("last_login"),
        }
        row = {k: v for k, v in row.items() if v is not None}
        _client.table("users").upsert(row, on_conflict="id").execute()
        logger.debug("☁️  Synced user %s", u.get("email"))
    except Exception as e:
        logger.error("☁️  _upsert_user failed: %s", e)


def _delete_user(user_id: int):
    if not _init(): return
    try:
        _client.table("users").delete().eq("id", user_id).execute()
        _client.table("complaints").delete().eq("user_id", user_id).execute()
        logger.info("☁️  Deleted user %s from cloud", user_id)
    except Exception as e:
        logger.error("☁️  _delete_user failed: %s", e)