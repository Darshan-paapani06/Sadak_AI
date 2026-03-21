"""
SADAK AI v2 — Database Layer
Users, Complaints, Timeline, Audit, Rate Limits
SQLite WAL mode — thread-safe
"""
import sqlite3, json, os, logging
from datetime import datetime, timedelta
from contextlib import contextmanager
from threading import Lock

logger  = logging.getLogger(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sadak_ai.db")
_lock   = Lock()

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name     TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            phone         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            state         TEXT,
            district      TEXT,
            role          TEXT    NOT NULL DEFAULT 'citizen',
            avatar_color  TEXT    DEFAULT '#0EA5E9',
            is_active     INTEGER NOT NULL DEFAULT 1,
            complaints_count INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT    NOT NULL,
            last_login    TEXT,
            admin_pin_hash TEXT DEFAULT NULL
        );
        CREATE TABLE IF NOT EXISTS complaints (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id     TEXT    UNIQUE NOT NULL,
            user_id          INTEGER,
            latitude         REAL    NOT NULL,
            longitude        REAL    NOT NULL,
            state            TEXT    NOT NULL,
            district         TEXT    NOT NULL,
            sub_district     TEXT,
            village          TEXT,
            severity         TEXT    NOT NULL DEFAULT 'MEDIUM',
            status           TEXT    NOT NULL DEFAULT 'FILED',
            description      TEXT,
            reporter_name    TEXT,
            reporter_phone   TEXT,
            image_path       TEXT,
            ai_detected      INTEGER NOT NULL DEFAULT 0,
            ai_confidence    REAL,
            ai_pothole_count INTEGER DEFAULT 0,
            ai_area_px2      REAL,
            ai_depth_score   REAL,
            authority_code   TEXT,
            authority_name   TEXT,
            authority_type   TEXT,
            helpline         TEXT,
            escalation       TEXT,
            response_deadline TEXT,
            resolved_at      TEXT,
            resolution_note  TEXT,
            escalated        INTEGER NOT NULL DEFAULT 0,
            filed_at         TEXT    NOT NULL,
            updated_at       TEXT    NOT NULL,
            extra_data       TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS complaint_timeline (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT    NOT NULL,
            event        TEXT    NOT NULL,
            note         TEXT,
            actor        TEXT,
            created_at   TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            action      TEXT    NOT NULL,
            entity      TEXT,
            entity_id   TEXT,
            user_id     INTEGER,
            ip_address  TEXT,
            details     TEXT,
            created_at  TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rate_limits (
            ip_address   TEXT NOT NULL,
            endpoint     TEXT NOT NULL,
            hit_count    INTEGER NOT NULL DEFAULT 1,
            window_start TEXT    NOT NULL,
            PRIMARY KEY (ip_address, endpoint)
        );
        CREATE INDEX IF NOT EXISTS idx_complaints_user   ON complaints(user_id);
        CREATE INDEX IF NOT EXISTS idx_complaints_state  ON complaints(state);
        CREATE INDEX IF NOT EXISTS idx_complaints_sev    ON complaints(severity);
        CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);
        CREATE INDEX IF NOT EXISTS idx_timeline_cid      ON complaint_timeline(complaint_id);
        """)
    # Safe migration for existing databases
    try:
        with get_db() as conn:
            conn.execute("ALTER TABLE users ADD COLUMN admin_pin_hash TEXT DEFAULT NULL")
            logger.info("Migrated: admin_pin_hash added")
    except Exception:
        pass  # Column already exists
    logger.info("DB ready: %s", DB_PATH)

# ── USERS ────────────────────────────────────────────────
def create_user(full_name, email, phone, password_hash, state=None, district=None):
    now = datetime.utcnow().isoformat()
    colors = ['#0EA5E9','#06B6D4','#10B981','#F59E0B','#F97316','#8B5CF6','#EC4899']
    import hashlib
    color = colors[int(hashlib.md5(email.encode()).hexdigest(), 16) % len(colors)]
    with _lock, get_db() as db:
        db.execute("""
            INSERT INTO users (full_name,email,phone,password_hash,state,district,avatar_color,created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (full_name, email.lower().strip(), phone.strip(), password_hash, state, district, color, now))
    return get_user_by_email(email)

def get_user_by_email(email):
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE email=? AND is_active=1", (email.lower().strip(),)).fetchone()
        return dict(row) if row else None

def get_user_by_id(user_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None

def update_last_login(user_id):
    with get_db() as db:
        db.execute("UPDATE users SET last_login=? WHERE id=?", (datetime.utcnow().isoformat(), user_id))

def increment_user_complaints(user_id):
    with get_db() as db:
        db.execute("UPDATE users SET complaints_count=complaints_count+1 WHERE id=?", (user_id,))


def get_user_by_phone(phone):
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE phone=? AND is_active=1", (phone.strip(),)).fetchone()
        return dict(row) if row else None

def email_exists(email):
    with get_db() as db:
        r = db.execute("SELECT 1 FROM users WHERE LOWER(email)=LOWER(?)", (email.strip(),)).fetchone()
        return r is not None

def phone_exists(phone):
    with get_db() as db:
        r = db.execute("SELECT 1 FROM users WHERE phone=?", (phone.strip(),)).fetchone()
        return r is not None

# ── COMPLAINTS ───────────────────────────────────────────
def insert_complaint(data: dict, user_id=None) -> str:
    now = datetime.utcnow().isoformat()
    with _lock, get_db() as db:
        db.execute("""
            INSERT INTO complaints (
                complaint_id,user_id,latitude,longitude,state,district,
                sub_district,village,severity,status,description,
                reporter_name,reporter_phone,image_path,
                ai_detected,ai_confidence,ai_pothole_count,ai_area_px2,ai_depth_score,
                authority_code,authority_name,authority_type,helpline,escalation,
                response_deadline,filed_at,updated_at,extra_data
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data["complaint_id"], user_id,
            data["latitude"], data["longitude"],
            data.get("state","Unknown"), data.get("district","Unknown"),
            data.get("sub_district"), data.get("village"),
            data.get("severity","MEDIUM"), "FILED",
            data.get("description"), data.get("reporter_name"), data.get("reporter_phone"),
            data.get("image_path"),
            1 if data.get("ai_detected") else 0,
            data.get("ai_confidence"), data.get("ai_pothole_count",0),
            data.get("ai_area_px2"), data.get("ai_depth_score"),
            data.get("authority_code"), data.get("authority_name"),
            data.get("authority_type"), data.get("helpline"), data.get("escalation"),
            data.get("response_deadline"), now, now,
            json.dumps(data.get("extra_data",{}))
        ))
        db.execute("""
            INSERT INTO complaint_timeline (complaint_id,event,note,actor,created_at)
            VALUES (?,?,?,?,?)
        """, (data["complaint_id"],"FILED","Complaint filed via SADAK AI Scanner","system",now))
    if user_id:
        increment_user_complaints(user_id)
    return data["complaint_id"]

def get_complaint(cid):
    with get_db() as db:
        row = db.execute("SELECT * FROM complaints WHERE complaint_id=?", (cid,)).fetchone()
        if not row: return None
        c = dict(row)
        c["timeline"] = [dict(r) for r in db.execute(
            "SELECT * FROM complaint_timeline WHERE complaint_id=? ORDER BY created_at", (cid,)
        ).fetchall()]
        return c

def get_complaints(filters=None):
    q = "SELECT c.*, u.full_name as user_name FROM complaints c LEFT JOIN users u ON c.user_id=u.id WHERE 1=1"
    p = []
    f = filters or {}
    if f.get("user_id"): q += " AND c.user_id=?"; p.append(f["user_id"])
    if f.get("state"):   q += " AND c.state=?";   p.append(f["state"])
    if f.get("severity"):q += " AND c.severity=?";p.append(f["severity"])
    if f.get("status"):  q += " AND c.status=?";  p.append(f["status"])
    q += " ORDER BY c.filed_at DESC LIMIT ?"; p.append(int(f.get("limit",100)))
    with get_db() as db:
        return [dict(r) for r in db.execute(q, p).fetchall()]

def update_complaint_status(cid, status, note="", actor="authority"):
    now = datetime.utcnow().isoformat()
    resolved_at = now if status=="RESOLVED" else None
    with _lock, get_db() as db:
        cur = db.execute("""
            UPDATE complaints SET status=?,updated_at=?,resolved_at=COALESCE(?,resolved_at)
            WHERE complaint_id=?
        """, (status, now, resolved_at, cid))
        if cur.rowcount == 0: return False
        db.execute("""
            INSERT INTO complaint_timeline (complaint_id,event,note,actor,created_at)
            VALUES (?,?,?,?,?)
        """, (cid, status, note or f"Status → {status}", actor, now))
    return True

def get_stats(user_id=None):
    where = f"WHERE user_id={user_id}" if user_id else ""
    with get_db() as db:
        r = db.execute(f"""
            SELECT
              COUNT(*)                                             AS total,
              SUM(CASE WHEN severity='CRITICAL' THEN 1 ELSE 0 END) AS critical,
              SUM(CASE WHEN severity='HIGH'     THEN 1 ELSE 0 END) AS high,
              SUM(CASE WHEN severity='MEDIUM'   THEN 1 ELSE 0 END) AS medium,
              SUM(CASE WHEN severity='LOW'      THEN 1 ELSE 0 END) AS low,
              SUM(CASE WHEN status='RESOLVED'   THEN 1 ELSE 0 END) AS resolved,
              SUM(CASE WHEN status='IN_PROGRESS' THEN 1 ELSE 0 END) AS in_progress,
              SUM(CASE WHEN status='ESCALATED'  THEN 1 ELSE 0 END) AS escalated,
              SUM(CASE WHEN ai_detected=1       THEN 1 ELSE 0 END) AS ai_detected,
              SUM(CASE WHEN date(filed_at)=date('now') THEN 1 ELSE 0 END) AS today
            FROM complaints {where}
        """).fetchone()
        st = db.execute("""
            SELECT state, COUNT(*) cnt FROM complaints GROUP BY state ORDER BY cnt DESC LIMIT 8
        """).fetchall()
    s = dict(r) if r else {}
    total = s.get("total",0) or 1
    s["resolution_rate"] = round((s.get("resolved",0) or 0)/total*100,1)
    s["by_state"] = [dict(x) for x in st]
    return s

def get_heatmap_data():
    with get_db() as db:
        rows = db.execute(
            "SELECT latitude,longitude,severity,status,complaint_id FROM complaints WHERE latitude IS NOT NULL"
        ).fetchall()
    return [dict(r) for r in rows]

def check_and_escalate():
    now = datetime.utcnow()
    escalated = []
    with get_db() as db:
        rows = db.execute("""
            SELECT complaint_id,severity,response_deadline FROM complaints
            WHERE status NOT IN ('RESOLVED','ESCALATED') AND response_deadline IS NOT NULL
        """).fetchall()
    for row in rows:
        try:
            if now > datetime.fromisoformat(row["response_deadline"]):
                update_complaint_status(row["complaint_id"],"ESCALATED",
                    "Auto-escalated: deadline missed → District Collector","system")
                escalated.append(row["complaint_id"])
        except Exception: pass
    return escalated

def check_rate_limit(ip, endpoint, max_hits=30, window_min=1):
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=window_min)
    with _lock, get_db() as db:
        row = db.execute("SELECT * FROM rate_limits WHERE ip_address=? AND endpoint=?", (ip,endpoint)).fetchone()
        if not row:
            db.execute("INSERT INTO rate_limits VALUES (?,?,1,?)", (ip,endpoint,now.isoformat()))
            return True
        if datetime.fromisoformat(row["window_start"]) < window_start:
            db.execute("UPDATE rate_limits SET hit_count=1,window_start=? WHERE ip_address=? AND endpoint=?",
                       (now.isoformat(),ip,endpoint))
            return True
        if row["hit_count"] >= max_hits: return False
        db.execute("UPDATE rate_limits SET hit_count=hit_count+1 WHERE ip_address=? AND endpoint=?", (ip,endpoint))
        return True

def log_audit(action, entity=None, entity_id=None, user_id=None, ip=None, details=None):
    with get_db() as db:
        db.execute("""
            INSERT INTO audit_log (action,entity,entity_id,user_id,ip_address,details,created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (action,entity,entity_id,user_id,ip,details,datetime.utcnow().isoformat()))

def update_password(user_id: int, new_hash: str) -> bool:
    """Update user password hash."""
    try:
        with _lock, get_db() as db:
            db.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, user_id))
        return True
    except Exception as e:
        logger.error("update_password error: %s", e)
        return False

def delete_complaint(complaint_id: str, user_id: int) -> dict:
    """Delete/withdraw a complaint. Only FILED status can be deleted by the user."""
    try:
        with _lock, get_db() as conn:
            row = conn.execute(
                "SELECT id, user_id, status FROM complaints WHERE complaint_id=?",
                (complaint_id.upper(),)
            ).fetchone()
            if not row:
                return {"success": False, "error": "Complaint not found."}
            if int(row["user_id"]) != int(user_id):
                return {"success": False, "error": "You can only withdraw your own complaints."}
            if row["status"] not in ("FILED",):
                return {"success": False, "error": f"Cannot withdraw a complaint with status '{row['status']}'. Only FILED complaints can be withdrawn."}
            conn.execute("DELETE FROM complaints WHERE id=?", (row["id"],))
            # Decrement user counter
            conn.execute("UPDATE users SET complaints_count = MAX(0, complaints_count-1) WHERE id=?", (user_id,))
        return {"success": True, "message": "Complaint withdrawn successfully."}
    except Exception as e:
        logger.error("delete_complaint error: %s", e)
        return {"success": False, "error": "Server error. Try again."}


def update_complaint_description(complaint_id: str, user_id: int, description: str) -> dict:
    """Allow user to update description only while status is FILED."""
    try:
        with _lock, get_db() as conn:
            row = conn.execute(
                "SELECT id, user_id, status FROM complaints WHERE complaint_id=?",
                (complaint_id.upper(),)
            ).fetchone()
            if not row:
                return {"success": False, "error": "Complaint not found."}
            if int(row["user_id"]) != int(user_id):
                return {"success": False, "error": "You can only edit your own complaints."}
            if row["status"] != "FILED":
                return {"success": False, "error": f"Cannot edit a complaint with status '{row['status']}'. Only FILED complaints can be edited."}
            conn.execute(
                "UPDATE complaints SET description=? WHERE id=?",
                (description.strip(), row["id"])
            )
        return {"success": True, "message": "Complaint updated successfully."}
    except Exception as e:
        logger.error("update_complaint_description error: %s", e)
        return {"success": False, "error": "Server error. Try again."}


def set_admin_pin(user_id: int, pin: str) -> bool:
    """Hash and store a 4–8 digit admin PIN for a user."""
    import hashlib
    pin_hash = hashlib.sha256((pin + "SADAK_ADMIN_PIN_SALT_2025").encode()).hexdigest()
    try:
        with _lock, get_db() as conn:
            conn.execute("UPDATE users SET admin_pin_hash=? WHERE id=?", (pin_hash, user_id))
        return True
    except Exception as e:
        logger.error("set_admin_pin error: %s", e)
        return False


def verify_admin_pin(user_id: int, pin: str) -> bool:
    """Verify the admin PIN for a user. Returns True if correct."""
    import hashlib
    pin_hash = hashlib.sha256((pin + "SADAK_ADMIN_PIN_SALT_2025").encode()).hexdigest()
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT admin_pin_hash FROM users WHERE id=? AND role IN ('admin','authority')",
                (user_id,)
            ).fetchone()
            if not row:
                return False
            stored = row["admin_pin_hash"]
            # If no PIN set yet, any 4+ digit PIN is accepted (first-time setup)
            if not stored:
                return len(pin) >= 4 and pin.isdigit()
            return stored == pin_hash
    except Exception as e:
        logger.error("verify_admin_pin error: %s", e)
        return False


def admin_has_pin(user_id: int) -> bool:
    """Check if admin has set a PIN."""
    try:
        with get_db() as conn:
            row = conn.execute("SELECT admin_pin_hash FROM users WHERE id=?", (user_id,)).fetchone()
            return bool(row and row["admin_pin_hash"])
    except:
        return False


def get_all_users() -> list:
    """Get all registered users for admin panel."""
    try:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT u.id, u.full_name, u.email, u.phone,
                       u.state, u.district, u.role,
                       u.complaints_count, u.created_at, u.last_login,
                       u.avatar_color, u.is_active,
                       COUNT(c.id) as total_complaints
                FROM users u
                LEFT JOIN complaints c ON c.user_id = u.id
                GROUP BY u.id
                ORDER BY u.created_at DESC
            """).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error("get_all_users error: %s", e)
        return []


def delete_user(user_id: int, admin_id: int) -> dict:
    """Hard delete a user account and all their complaints. Admin only."""
    try:
        if int(user_id) == int(admin_id):
            return {"success": False, "error": "Admin cannot delete their own account."}
        with _lock, get_db() as conn:
            row = conn.execute("SELECT id, full_name, email, role FROM users WHERE id=?",
                               (user_id,)).fetchone()
            if not row:
                return {"success": False, "error": "User not found."}
            if row["role"] == "admin":
                return {"success": False, "error": "Cannot delete another admin account."}
            # Delete all complaints by this user first
            conn.execute("DELETE FROM complaint_timeline WHERE complaint_id IN "
                         "(SELECT complaint_id FROM complaints WHERE user_id=?)", (user_id,))
            conn.execute("DELETE FROM complaints WHERE user_id=?", (user_id,))
            # Delete the user
            conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        return {"success": True,
                "message": f"Account '{row['full_name']}' ({row['email']}) deleted. "
                           f"They must register again to use SADAK AI."}
    except Exception as e:
        logger.error("delete_user error: %s", e)
        return {"success": False, "error": "Server error. Try again."}


def toggle_user_status(user_id: int, admin_id: int) -> dict:
    """Suspend or reactivate a user account."""
    try:
        if int(user_id) == int(admin_id):
            return {"success": False, "error": "Cannot suspend your own account."}
        with _lock, get_db() as conn:
            row = conn.execute("SELECT id, full_name, is_active, role FROM users WHERE id=?",
                               (user_id,)).fetchone()
            if not row:
                return {"success": False, "error": "User not found."}
            if row["role"] == "admin":
                return {"success": False, "error": "Cannot suspend another admin account."}
            new_status = 0 if row["is_active"] else 1
            conn.execute("UPDATE users SET is_active=? WHERE id=?", (new_status, user_id))
            action = "reactivated" if new_status else "suspended"
        return {"success": True, "active": bool(new_status),
                "message": f"Account '{row['full_name']}' {action} successfully."}
    except Exception as e:
        logger.error("toggle_user_status error: %s", e)
        return {"success": False, "error": "Server error. Try again."}