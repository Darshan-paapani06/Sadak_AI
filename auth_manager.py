"""
SADAK AI v2 — Auth Manager
Version-safe JWT (works with PyJWT 1.x and 2.x)
"""
import os, hashlib, hmac, re, functools, logging
from datetime import datetime, timedelta, timezone
from flask import request, jsonify, g

logger = logging.getLogger(__name__)

_SECRET  = "SADAK2025IndiaRoadGuardian_FixedKey_XyZ"
JWT_ALG  = "HS256"
UPLOAD_LIMIT = 10 * 1024 * 1024
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# ── Detect PyJWT version and import correctly ─────────────
try:
    import jwt as _jwt
    _JWT_VERSION = int((_jwt.__version__ or "2").split(".")[0])
except Exception:
    _JWT_VERSION = 2

def _encode_token(payload):
    try:
        token = _jwt.encode(payload, _SECRET, algorithm=JWT_ALG)
        # PyJWT < 2.0 returns bytes
        if isinstance(token, bytes):
            return token.decode("utf-8")
        return token
    except Exception as e:
        logger.error("JWT encode error: %s", e)
        return None

def _decode_token_internal(token):
    try:
        # Try with options for newer versions
        return _jwt.decode(token, _SECRET, algorithms=[JWT_ALG])
    except Exception:
        pass
    try:
        # Try without options for older versions
        return _jwt.decode(token, _SECRET, algorithm=JWT_ALG)
    except Exception:
        pass
    try:
        # Try with verify=False to check structure (debug only)
        options = {"verify_signature": False}
        return _jwt.decode(token, options=options, algorithms=[JWT_ALG])
    except Exception as e:
        logger.debug("All JWT decode attempts failed: %s", e)
        return None

# ── PASSWORDS ─────────────────────────────────────────────
def hash_password(password):
    salt = os.urandom(16).hex()
    dk   = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310000)
    return "pbkdf2:sha256:" + salt + ":" + dk.hex()

def verify_password(password, stored):
    try:
        parts  = stored.split(":")
        salt   = parts[2]
        dk_hex = parts[3]
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310000)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False

# ── JWT ───────────────────────────────────────────────────
def generate_token(user_id, email, full_name, role):
    now = datetime.now(timezone.utc)
    payload = {
        "sub":   user_id,
        "email": email,
        "name":  full_name,
        "role":  role,
        "iat":   int(now.timestamp()),
        "exp":   int((now + timedelta(days=30)).timestamp()),
    }
    return _encode_token(payload)

def decode_token(token):
    if not token:
        return None
    return _decode_token_internal(token)

def get_token_from_request():
    # 1. URL query param
    t = (request.args.get("token") or "").strip()
    if t: return t
    # 2. Authorization header
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        t = auth[7:].strip()
        if t: return t
    # 3. Cookie
    t = (request.cookies.get("sadak_token") or "").strip()
    if t: return t
    return None

def require_auth(roles=None):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            token = get_token_from_request()
            if not token:
                return jsonify({"error": "Authentication required", "code": "NO_AUTH"}), 401
            payload = decode_token(token)
            if not payload:
                return jsonify({"error": "Invalid or expired session", "code": "INVALID_TOKEN"}), 401
            
            # If role check needed, ALWAYS verify from live DB
            # This handles stale JWTs after role changes
            if roles:
                try:
                    from database import get_user_by_id as _get_user
                    db_user = _get_user(payload.get("sub"))
                    live_role = db_user.get("role", "citizen") if db_user else payload.get("role", "citizen")
                except Exception:
                    live_role = payload.get("role", "citizen")
                
                if live_role not in roles:
                    return jsonify({"error": "Permission denied", "code": "FORBIDDEN"}), 403
                # Update payload with live role so routes can use g.user.get("role")
                payload["role"] = live_role
            
            g.user = payload
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def validate_registration(data):
    errors = []
    name  = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    pwd   = data.get("password", "")
    if len(name) < 2:
        errors.append("Full name must be at least 2 characters")
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        errors.append("Invalid email address")
    phone_clean = re.sub(r'[\s\-\+\(\)]', '', phone)
    if not re.match(r'^\d{10,12}$', phone_clean):
        errors.append("Invalid mobile number")
    if len(pwd) < 8:
        errors.append("Password must be at least 8 characters")
    if not re.search(r'[A-Z]', pwd):
        errors.append("Password needs at least one uppercase letter")
    if not re.search(r'\d', pwd):
        errors.append("Password needs at least one number")
    return errors

def validate_login(data):
    errors = []
    if not data.get("email"):    errors.append("Email required")
    if not data.get("password"): errors.append("Password required")
    return errors

def validate_upload(file_obj):
    if not file_obj: return False, "No file"
    ext = os.path.splitext(file_obj.filename or "")[1].lower()
    if ext not in ALLOWED_EXTS: return False, "Use JPG or PNG"
    file_obj.seek(0, 2); size = file_obj.tell(); file_obj.seek(0)
    if size > UPLOAD_LIMIT: return False, "Max 10MB"
    if size < 100: return False, "File too small"
    return True, ""

def validate_coordinates(lat, lng):
    try:
        lat = float(lat); lng = float(lng)
        if 6.0 <= lat <= 37.5 and 68.0 <= lng <= 97.5:
            return True, ""
        return False, "Coordinates outside India"
    except Exception:
        return False, "Invalid coordinates"

def sanitize(val, maxlen=500):
    return str(val or "").strip()[:maxlen]

def get_client_ip():
    xff = request.headers.get("X-Forwarded-For", "")
    if xff: return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"