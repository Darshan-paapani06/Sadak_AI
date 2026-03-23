"""
SADAK AI v3 - Flask Application
"""
import os, sys
try:
    from dotenv import load_dotenv
    load_dotenv()  # loads .env file automatically
except ImportError:
    pass  # python-dotenv optional
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
sys.path.insert(0, BASE_DIR)

import json, time, uuid, queue, threading, logging, re
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, request, jsonify, render_template, Response, send_from_directory, g, redirect

from database import (init_db, create_user, get_user_by_email, get_user_by_id, get_user_by_phone,
                      update_last_login, email_exists, phone_exists,
                      insert_complaint, get_complaint, get_complaints,
                      update_complaint_status, get_stats, get_heatmap_data,
                      log_audit, check_rate_limit, update_password,
                      delete_complaint, update_complaint_description,
                      set_admin_pin, verify_admin_pin, admin_has_pin,
                      get_all_users, delete_user, toggle_user_status)
from detector import get_detector
from auth_manager import (require_auth, hash_password, verify_password, generate_token,
                          decode_token, get_token_from_request, validate_registration,
                          validate_login, validate_upload, validate_coordinates,
                          sanitize, get_client_ip)
from location_router import get_authority, validate_coordinates as lv, get_response_deadline
from complaint_engine import build_complaint, format_complaint_response
from otp_manager import send_otp, verify_otp, send_reset_otp, verify_reset_otp
from location_api import get_states, get_districts, get_localities
# ── CLOUD SYNC (Supabase) ─────────────────────────────────
try:
    from cloud_sync import (
        sync_complaint_filed, sync_complaint_updated,
        sync_user_created, sync_user_deleted, sync_user_updated
    )
    CLOUD_SYNC = True
except ImportError:
    CLOUD_SYNC = False
    def sync_complaint_filed(c): pass
    def sync_complaint_updated(c): pass
    def sync_user_created(u): pass
    def sync_user_deleted(uid): pass
    def sync_user_updated(u): pass

try:
    from pdf_generator import generate_complaint_pdf as _gen_pdf
    PDF_OK = True
except ImportError:
    PDF_OK = False
    _gen_pdf = None

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("sadak_ai")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.update(
    SECRET_KEY="SADAK2025IndiaRoadGuardian_FixedKey_XyZ",
    MAX_CONTENT_LENGTH=12 * 1024 * 1024,
)

# ── SSE ──────────────────────────────────────────────────
_subs = []
_sub_lock = threading.Lock()

def _broadcast(event_type, data):
    msg = json.dumps({"type": event_type, "data": data,
                      "ts": datetime.now(timezone.utc).isoformat()})
    dead = []
    with _sub_lock:
        for q in _subs:
            try: q.put_nowait(msg)
            except queue.Full: dead.append(q)
        for q in dead: _subs.remove(q)

def _sse_stream():
    q = queue.Queue(maxsize=40)
    with _sub_lock: _subs.append(q)
    try:
        yield "data: " + json.dumps({"type": "connected"}) + "\n\n"
        while True:
            try: yield "data: " + q.get(timeout=20) + "\n\n"
            except queue.Empty: yield ": keepalive\n\n"
    finally:
        with _sub_lock:
            if q in _subs: _subs.remove(q)

def rate_limited(max_hits=30, window_min=1):
    def dec(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not check_rate_limit(get_client_ip(), request.endpoint, max_hits, window_min):
                return jsonify({"error": "Too many requests. Please wait."}), 429
            return fn(*args, **kwargs)
        return wrapper
    return dec

def _safe_user(u):
    keys = ["id","full_name","email","phone","state","district",
            "role","avatar_color","complaints_count","created_at"]
    return {k: u[k] for k in keys if k in u}

threading.Thread(target=lambda: [time.sleep(300) or None], daemon=True).start()

# ═══════════════════════════════════════════
#  PAGES
# ═══════════════════════════════════════════
@app.route("/")
def index(): return render_template("login.html")

@app.route("/home")
def home(): return render_template("home.html")

@app.route("/scanner")
def scanner(): return render_template("scanner.html")

@app.route("/auto-report")
def auto_report(): return render_template("auto_report.html")

@app.route("/history")
def history(): return render_template("history.html")

@app.route("/admin")
def admin():
    # Get token from cookie, query param, or Authorization header
    token = (request.cookies.get("sadak_token") or
             request.args.get("token") or
             request.headers.get("Authorization","").replace("Bearer ","").strip())
    
    if not token:
        # No token at all - send to admin landing that will grab from localStorage
        return render_template("admin.html")
    
    payload = decode_token(token)
    if not payload:
        return render_template("admin.html")  # Let JS handle redirect
    
    # Check LIVE DB role - token may be stale
    try:
        db_user = get_user_by_id(payload.get("sub"))
        live_role = db_user.get("role", "citizen") if db_user else "citizen"
    except Exception:
        live_role = payload.get("role", "citizen")
    
    if live_role not in ("admin", "authority"):
        return render_template("admin.html")  # Let JS show access denied
    
    return render_template("admin.html")

@app.route("/uploads/<path:filename>")
def serve_upload(filename): return send_from_directory(UPLOAD_DIR, filename)

@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(os.path.join(BASE_DIR, "static"), filename)

@app.route("/sw.js")
def service_worker():
    return send_from_directory(os.path.join(BASE_DIR, "static"), "sw.js",
                               mimetype="application/javascript",
                               headers={"Cache-Control": "no-cache",
                                        "Service-Worker-Allowed": "/"})

@app.route("/manifest.json")
def manifest():
    return send_from_directory(os.path.join(BASE_DIR, "static"), "manifest.json",
                               mimetype="application/manifest+json")

@app.route("/api/stream")
def stream():
    return Response(_sse_stream(), mimetype="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no","Connection":"keep-alive"})

# ═══════════════════════════════════════════
#  OTP AUTH  ← NOT CHANGED — DO NOT TOUCH
# ═══════════════════════════════════════════
@app.route("/api/auth/send-otp", methods=["POST"])
@rate_limited(max_hits=10, window_min=1)
def api_send_otp():
    try:
        data  = request.get_json(silent=True) or {}
        email = (data.get("email") or "").lower().strip()
        if not email or "@" not in email or "." not in email:
            return jsonify({"success": False, "message": "Enter a valid email address."}), 400
        result = send_otp(email)
        logger.info("send_otp result for %s: %s", email, result)
        return jsonify(result)
    except Exception as e:
        logger.error("send-otp error: %s", e)
        return jsonify({"success": False, "message": "Server error. Please try again."}), 500

@app.route("/api/auth/register", methods=["POST"])
@rate_limited(max_hits=10, window_min=5)
def register():
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").lower().strip()
    otp   = (data.get("otp") or "").strip()

    if email_exists(email):
        return jsonify({"error": "This email is already registered. Please sign in instead."}), 409

    ok, err = verify_otp(email, otp)
    if not ok:
        return jsonify({"error": err}), 400

    errors = validate_registration(data)
    if errors:
        return jsonify({"error": errors[0]}), 400

    phone_clean = re.sub(r'[\s\-\+\(\)]', '', data["phone"].strip())

    if phone_exists(phone_clean):
        return jsonify({"error": "This mobile number is already registered. Please sign in instead."}), 409

    user = create_user(
        full_name     = sanitize(data["full_name"], 100),
        email         = email,
        phone         = phone_clean,
        password_hash = hash_password(data["password"]),
        state         = sanitize(data.get("state", ""), 60),
        district      = sanitize(data.get("district", ""), 60),
    )
    if not user:
        return jsonify({"error": "Registration failed. Try again."}), 500

    token = generate_token(user["id"], user["email"], user["full_name"], user["role"])
    log_audit("REGISTER", "user", str(user["id"]), user["id"], get_client_ip())
    sync_user_created(dict(user))
    return jsonify({"token": token, "user": _safe_user(user)}), 201

@app.route("/api/auth/login", methods=["POST"])
@rate_limited(max_hits=15, window_min=5)
def login():
    data       = request.get_json(silent=True) or {}
    identifier = (data.get("email") or data.get("phone") or "").strip()
    password   = (data.get("password") or "").strip()

    if not identifier:
        return jsonify({"error": "Email or mobile number is required"}), 400
    if not password:
        return jsonify({"error": "Password is required"}), 400

    user = None
    if "@" in identifier:
        user = get_user_by_email(identifier.lower())
    else:
        phone_clean = re.sub(r"[\s\-\+\(\)]", "", identifier)
        user = get_user_by_phone(phone_clean)

    if not user or not verify_password(password, user["password_hash"]):
        log_audit("LOGIN_FAIL", ip=get_client_ip(), details=identifier)
        return jsonify({"error": "Invalid credentials. Please check and try again."}), 401

    update_last_login(user["id"])
    token = generate_token(user["id"], user["email"], user["full_name"], user["role"])
    log_audit("LOGIN_OK", "user", str(user["id"]), user["id"], get_client_ip())
    return jsonify({"token": token, "user": _safe_user(user)})

@app.route("/api/auth/me")
@require_auth()
def me():
    user = get_user_by_id(g.user["sub"])
    if not user: return jsonify({"error": "User not found"}), 404
    return jsonify({"user": _safe_user(user), "stats": get_stats(user_id=user["id"])})

@app.route("/api/auth/verify")
def verify():
    token = get_token_from_request()
    if not token: return jsonify({"valid": False})
    p = decode_token(token)
    if not p: return jsonify({"valid": False})
    # Always read role from DB — token may be stale after admin role grant
    user = get_user_by_id(p.get("sub"))
    live_role = user.get("role", "citizen") if user else p.get("role", "citizen")
    return jsonify({"valid": True, "user": {
        "name": p.get("name"),
        "role": live_role,
        "sub":  p.get("sub")
    }})


# ═══════════════════════════════════════════
#  FORGOT PASSWORD — EMAIL RESET
# ═══════════════════════════════════════════
@app.route("/api/auth/forgot-password", methods=["POST"])
@rate_limited(max_hits=5, window_min=10)
def forgot_password():
    """Step 1: Send reset OTP to registered email."""
    try:
        data  = request.get_json(silent=True) or {}
        email = (data.get("email") or "").lower().strip()
        if not email or "@" not in email:
            return jsonify({"success": False, "message": "Enter a valid email address."}), 400
        # Check if email is registered — tell user clearly
        if not email_exists(email):
            return jsonify({
                "success": False,
                "not_registered": True,
                "message": f"No account found with {email}. Please register first."
            })
        result = send_reset_otp(email)
        return jsonify(result)
    except Exception as e:
        logger.error("forgot-password error: %s", e)
        return jsonify({"success": False, "message": "Server error. Try again."}), 500

@app.route("/api/auth/reset-password", methods=["POST"])
@rate_limited(max_hits=5, window_min=10)
def reset_password():
    """Step 2: Verify OTP + set new password."""
    try:
        data     = request.get_json(silent=True) or {}
        email    = (data.get("email") or "").lower().strip()
        otp      = (data.get("otp") or "").strip()
        new_pass = (data.get("password") or "").strip()

        if not email:
            return jsonify({"error": "Email is required."}), 400
        if not otp or len(otp) != 6:
            return jsonify({"error": "Enter the 6-digit reset code."}), 400
        if not new_pass or len(new_pass) < 8:
            return jsonify({"error": "Password must be at least 8 characters."}), 400

        ok, err = verify_reset_otp(email, otp)
        if not ok:
            return jsonify({"error": err}), 400

        user = get_user_by_email(email)
        if not user:
            return jsonify({"error": "Account not found."}), 404

        # Update password in database
        new_hash = hash_password(new_pass)
        from database import update_password, delete_complaint, update_complaint_description
        updated  = update_password(user["id"], new_hash)
        if not updated:
            return jsonify({"error": "Could not update password. Try again."}), 500

        log_audit("PASSWORD_RESET", "user", str(user["id"]), user["id"], get_client_ip())
        return jsonify({"success": True, "message": "Password updated successfully. Please sign in."})

    except Exception as e:
        logger.error("reset-password error: %s", e)
        return jsonify({"error": "Server error. Try again."}), 500


# ═══════════════════════════════════════════════════
#  DELETE / WITHDRAW COMPLAINT
# ═══════════════════════════════════════════════════
@app.route("/api/complaints/<cid>/withdraw", methods=["DELETE","POST"])
@require_auth()
def withdraw_complaint(cid):
    try:
        uid = g.user["sub"]
        result = delete_complaint(cid.upper(), uid)
        if result["success"]:
            log_audit("COMPLAINT_WITHDRAWN", "complaint", cid.upper(), uid, get_client_ip())
            return jsonify(result)
        return jsonify(result), 400
    except Exception as e:
        logger.error("withdraw_complaint error: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════
#  EDIT COMPLAINT DESCRIPTION
# ═══════════════════════════════════════════════════
@app.route("/api/complaints/<cid>/edit", methods=["PUT","POST"])
@require_auth()
def edit_complaint(cid):
    try:
        uid  = g.user["sub"]
        data = request.get_json(silent=True) or {}
        desc = (data.get("description") or "").strip()
        if not desc or len(desc) < 5:
            return jsonify({"success": False, "error": "Description must be at least 5 characters."}), 400
        if len(desc) > 500:
            return jsonify({"success": False, "error": "Description too long (max 500 chars)."}), 400
        result = update_complaint_description(cid.upper(), uid, desc)
        if result["success"]:
            log_audit("COMPLAINT_EDITED", "complaint", cid.upper(), uid, get_client_ip())
            return jsonify(result)
        return jsonify(result), 400
    except Exception as e:
        logger.error("edit_complaint error: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════
#  ADMIN PIN — VERIFY & SET
# ═══════════════════════════════════════════════════
@app.route("/api/admin/verify-pin", methods=["POST"])
@require_auth()
def verify_pin_route():
    """Verify admin PIN. Returns has_pin flag + valid status."""
    try:
        uid  = g.user["sub"]
        data = request.get_json(silent=True) or {}
        pin  = str(data.get("pin","")).strip()
        has  = admin_has_pin(uid)
        if not pin:
            return jsonify({"has_pin": has, "valid": False, "error": "PIN required"})
        ok = verify_admin_pin(uid, pin)
        if ok and not has:
            # First login — save this PIN automatically
            set_admin_pin(uid, pin)
        log_audit("ADMIN_PIN_VERIFY", "user", str(uid), uid, get_client_ip())
        return jsonify({"has_pin": has, "valid": ok})
    except Exception as e:
        logger.error("verify_pin error: %s", e)
        return jsonify({"error": "Server error"}), 500


@app.route("/api/admin/set-pin", methods=["POST"])
@require_auth()
def set_pin_route():
    """Set or change admin PIN."""
    try:
        uid  = g.user["sub"]
        data = request.get_json(silent=True) or {}
        pin  = str(data.get("pin","")).strip()
        if not pin.isdigit() or len(pin) < 4 or len(pin) > 8:
            return jsonify({"success": False, "error": "PIN must be 4–8 digits."}), 400
        ok = set_admin_pin(uid, pin)
        if ok:
            log_audit("ADMIN_PIN_SET", "user", str(uid), uid, get_client_ip())
            return jsonify({"success": True, "message": "Admin PIN updated successfully."})
        return jsonify({"success": False, "error": "Failed to save PIN."}), 500
    except Exception as e:
        logger.error("set_pin error: %s", e)
        return jsonify({"error": "Server error"}), 500


@app.route("/api/admin/has-pin")
@require_auth()
def has_pin_route():
    return jsonify({"has_pin": admin_has_pin(g.user["sub"])})

# ═══════════════════════════════════════════
#  SCANNER
# ═══════════════════════════════════════════
@app.route("/api/detect-frame", methods=["POST"])
@require_auth()
@rate_limited(max_hits=120, window_min=1)
def detect_frame():
    frame_data = None
    if request.content_type and "image" in request.content_type:
        frame_data = request.get_data()
    elif request.files.get("frame"):
        frame_data = request.files["frame"].read()
    if not frame_data or len(frame_data) < 500:
        return jsonify({"detected": False, "confidence": 0, "severity": "UNKNOWN"}), 400
    result = get_detector().detect(frame_data, scanner_mode=True)
    return jsonify({
        "detected":       result.detected,
        "severity":       result.severity,
        "confidence":     result.confidence,
        "pothole_count":  result.pothole_count,
        "bounding_boxes": result.bounding_boxes,
        "processing_ms":  result.processing_ms,
    })

# ═══════════════════════════════════════════
#  COMPLAINTS
# ═══════════════════════════════════════════
@app.route("/api/report/pothole", methods=["POST"])
@require_auth()
@rate_limited(max_hits=20, window_min=1)
def report_pothole():
    user_id = g.user["sub"]
    try:
        lat = float(request.form.get("latitude", 0))
        lng = float(request.form.get("longitude", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid coordinates"}), 400

    ok, err = validate_coordinates(lat, lng)
    if not ok: return jsonify({"error": err}), 400

    severity       = sanitize(request.form.get("severity", "MEDIUM"), 20).upper()
    description    = sanitize(request.form.get("description", ""), 1000)
    reporter_name  = sanitize(request.form.get("reporter_name", ""), 120)
    reporter_phone = sanitize(request.form.get("reporter_phone", ""), 20)
    is_village     = request.form.get("is_village", "false").lower() == "true"

    if severity not in ("CRITICAL","HIGH","MEDIUM","LOW"): severity = "MEDIUM"
    if not reporter_name:
        user = get_user_by_id(user_id)
        if user:
            reporter_name  = user["full_name"]
            reporter_phone = reporter_phone or user["phone"]

    image_path = None
    detection  = None
    file = request.files.get("image")
    if file and file.filename:
        ok, err = validate_upload(file)
        if not ok: return jsonify({"error": err}), 400
        ext       = os.path.splitext(file.filename)[1].lower() or ".jpg"
        safe_name = uuid.uuid4().hex + ext
        file.save(os.path.join(UPLOAD_DIR, safe_name))
        image_path = safe_name
        try: detection = get_detector().detect(os.path.join(UPLOAD_DIR, safe_name))
        except Exception as e: logger.warning("Detection: %s", e)

    try:
        data = build_complaint(lat=lat, lng=lng, severity=severity,
            description=description, reporter_name=reporter_name,
            reporter_phone=reporter_phone, image_path=image_path,
            detection=detection, is_village=is_village)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    cid = insert_complaint(data, user_id=user_id)
    log_audit("COMPLAINT_FILED", "complaint", cid, user_id, get_client_ip())
    c   = get_complaint(cid)
    fmt = format_complaint_response(c)
    _broadcast("new_complaint", fmt)
    _broadcast("stats_updated", get_stats())
    # ── Cloud sync ──
    sync_complaint_filed(fmt)
    return jsonify({"success": True, "complaint": fmt,
                    "ai_result": detection.to_dict() if detection else None}), 201

@app.route("/api/complaints")
@require_auth()
@rate_limited(max_hits=60)
def list_complaints():
    role    = g.user.get("role", "citizen")
    max_limit = 500 if role in ("admin","authority") else 200
    filters = {
        "state":    request.args.get("state"),
        "severity": request.args.get("severity"),
        "status":   request.args.get("status"),
        "limit":    min(int(request.args.get("limit", 50)), max_limit),
    }
    if role == "citizen": filters["user_id"] = g.user["sub"]
    return jsonify([format_complaint_response(r) for r in get_complaints(filters)])

@app.route("/api/complaints/<cid>")
@require_auth()
def get_one(cid):
    c = get_complaint(cid.upper())
    if not c: return jsonify({"error": "Not found"}), 404
    return jsonify(format_complaint_response(c))

@app.route("/api/complaints/<cid>/status", methods=["PUT"])
@require_auth(roles=["admin","authority"])
def update_status(cid):
    body   = request.get_json(silent=True) or {}
    status = sanitize(body.get("status",""), 30).upper()
    note   = sanitize(body.get("note",""), 500)
    if status not in ("ACKNOWLEDGED","IN_PROGRESS","RESOLVED","ESCALATED"):
        return jsonify({"error": "Invalid status"}), 400
    ok = update_complaint_status(cid.upper(), status, note, g.user.get("name","authority"))
    if not ok: return jsonify({"error": "Not found"}), 404
    c = get_complaint(cid.upper())
    fmt = format_complaint_response(c)
    _broadcast("complaint_updated", fmt)
    sync_complaint_updated(fmt)
    return jsonify({"success": True, "complaint": fmt})

@app.route("/api/stats")
@require_auth()
def stats():
    uid = g.user["sub"] if g.user.get("role","citizen") == "citizen" else None
    return jsonify(get_stats(user_id=uid))

@app.route("/api/heatmap")
@require_auth()
def heatmap(): return jsonify(get_heatmap_data())

@app.route("/api/geocode")
@require_auth()
@rate_limited(max_hits=30)
def geocode():
    try: lat = float(request.args["lat"]); lng = float(request.args["lng"])
    except: return jsonify({"error": "Invalid coords"}), 400
    if not lv(lat, lng): return jsonify({"error": "Outside India"}), 400
    return jsonify(get_authority(lat, lng).to_dict())

# ═══════════════════════════════════════════
#  LOCATION API
# ═══════════════════════════════════════════
@app.route("/api/location/states")
def api_states():
    return jsonify(get_states())

@app.route("/api/location/districts")
def api_districts():
    state = request.args.get("state","").strip()
    if not state: return jsonify([])
    return jsonify(get_districts(state))

@app.route("/api/location/localities")
def api_localities():
    state    = request.args.get("state","").strip()
    district = request.args.get("district","").strip()
    if not state or not district: return jsonify([])
    return jsonify(get_localities(state, district))

# ═══════════════════════════════════════════
#  PDF COMPLAINT DOWNLOAD
# ═══════════════════════════════════════════
@app.route("/api/complaints/<cid>/pdf")
@require_auth()
def download_pdf(cid):
    comp = get_complaint(cid.upper())
    if not comp:
        return jsonify({"error": "Complaint not found."}), 404

    try:
        complaint_data = dict(comp)
        # Security: citizens can only download their own
        user_role = g.user.get("role", "citizen")
        user_id   = g.user["sub"]
        if user_role not in ("admin", "authority") and complaint_data.get("user_id") != user_id:
            return jsonify({"error": "Access denied."}), 403

        # Enrich with user data for PDF
        user = get_user_by_id(complaint_data.get("user_id"))
        if user:
            complaint_data.setdefault("user_name",  user.get("full_name", "Citizen"))
            complaint_data.setdefault("user_email", user.get("email", ""))
            complaint_data.setdefault("user_phone", user.get("phone", ""))

        from flask import send_file
        import tempfile
        if not PDF_OK:
            # Try importing again with explicit path
            import importlib.util, sys
            spec = importlib.util.spec_from_file_location('pdf_generator', os.path.join(BASE_DIR,'pdf_generator.py'))
            _mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_mod)
            generate_complaint_pdf = _mod.generate_complaint_pdf
        else:
            generate_complaint_pdf = _gen_pdf

        # Write to temp file to avoid conflicts
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            pdf_path = tmp.name

        ok = generate_complaint_pdf(complaint_data, pdf_path)
        if ok and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 100:
            pdf_name = f"SADAK-{cid.upper()}.pdf"
            return send_file(
                pdf_path,
                as_attachment=True,
                download_name=pdf_name,
                mimetype="application/pdf"
            )
        return jsonify({"error": "PDF could not be generated. Try again."}), 500

    except Exception as e:
        logger.error("PDF generation error for %s: %s", cid, e, exc_info=True)
        return jsonify({"error": "PDF error: " + str(e)[:120]}), 500

@app.route("/api/road-quality")
@require_auth()
@rate_limited(max_hits=30)
def road_quality():
    district = request.args.get("district","").strip()
    state    = request.args.get("state","").strip()
    if district and state:
        from road_quality import calculate_district_score
        s = calculate_district_score(district, state)
        return jsonify({
            "zone": s.zone, "zone_type": s.zone_type,
            "score": s.score, "grade": s.grade,
            "total_reports": s.total_reports,
            "critical": s.critical, "high": s.high,
            "resolved_pct": s.resolved_pct,
            "trend": s.trend, "worst_spots": s.worst_spots,
        })
    from road_quality import calculate_state_scores
    return jsonify(calculate_state_scores())

@app.route("/api/road-quality/india")
@require_auth()
def india_quality():
    from road_quality import calculate_state_scores
    scores = calculate_state_scores()
    if not scores:
        return jsonify({"average_score": 100, "states": [], "worst_state": None, "best_state": None})
    avg = sum(s["score"] for s in scores) // len(scores)
    return jsonify({
        "average_score": avg,
        "total_states":  len(scores),
        "worst_state":   scores[0]  if scores else None,
        "best_state":    scores[-1] if scores else None,
        "all_states":    scores,
    })

# ═══════════════════════════════════════════
#  LANGUAGE SUPPORT — 22 Indian Languages
# ═══════════════════════════════════════════
@app.route("/api/languages")
def get_languages():
    from language_support import get_language_list
    return jsonify(get_language_list())

@app.route("/api/translate", methods=["POST"])
@require_auth()
@rate_limited(max_hits=20)
def translate():
    data = request.get_json(silent=True) or {}
    text = sanitize(data.get("text",""), 500)
    lang = sanitize(data.get("lang","en"), 10)
    if not text or not lang:
        return jsonify({"error": "text and lang required"}), 400
    from language_support import translate_text
    return jsonify({"original": text, "translated": translate_text(text, lang), "lang": lang})

@app.route("/api/ui-strings")
def ui_strings():
    lang = request.args.get("lang","en")
    from language_support import UI_STRINGS
    return jsonify({k: v.get(lang) or v.get("en") or k for k, v in UI_STRINGS.items()})

# ═══════════════════════════════════════════
#  ADMIN APIs
# ═══════════════════════════════════════════
@app.route("/api/admin/stats")
@require_auth()
def admin_stats():
    return jsonify(get_stats())

@app.route("/api/admin/export")
@require_auth(roles=["admin"])
def export_complaints():
    data = get_complaints({"limit": 10000})
    return jsonify([format_complaint_response(r) for r in data])


# ═══════════════════════════════════════════════════
#  ADMIN — USER MANAGEMENT
# ═══════════════════════════════════════════════════
@app.route("/api/admin/users")
@require_auth(roles=["admin"])
def admin_get_users():
    """Get all registered users for admin panel."""
    users = get_all_users()
    return jsonify(users)


@app.route("/api/admin/users/<int:uid>/delete", methods=["POST","DELETE"])
@require_auth(roles=["admin"])
def admin_delete_user(uid):
    """Permanently delete a user account and all their data."""
    admin_id = g.user["sub"]
    result = delete_user(uid, admin_id)
    if result["success"]:
        log_audit("USER_DELETED", "user", str(uid), admin_id, get_client_ip())
    return jsonify(result), 200 if result["success"] else 400


@app.route("/api/admin/users/<int:uid>/toggle", methods=["POST"])
@require_auth(roles=["admin"])
def admin_toggle_user(uid):
    """Suspend or reactivate a user account."""
    admin_id = g.user["sub"]
    result = toggle_user_status(uid, admin_id)
    if result["success"]:
        log_audit("USER_TOGGLED", "user", str(uid), admin_id, get_client_ip())
    return jsonify(result), 200 if result["success"] else 400


@app.route("/api/admin/users/<int:uid>/make-admin", methods=["POST"])
@require_auth(roles=["admin"])
def admin_make_admin(uid):
    """Grant or revoke admin role for a user."""
    admin_id = g.user["sub"]
    if int(uid) == int(admin_id):
        return jsonify({"success": False, "error": "Cannot change your own role."}), 400
    try:
        db_user = get_user_by_id(uid)
        if not db_user:
            return jsonify({"success": False, "error": "User not found."}), 404
        new_role = "citizen" if db_user.get("role") == "admin" else "admin"
        from database import get_db, _lock
        import threading
        with get_db() as conn:
            conn.execute("UPDATE users SET role=? WHERE id=?", (new_role, uid))
        log_audit("ROLE_CHANGED", "user", str(uid), admin_id, get_client_ip())
        if db_user: sync_user_updated({**dict(db_user), "role": new_role})
        return jsonify({"success": True, "new_role": new_role,
                        "message": f"Role changed to {new_role}."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════
#  ADMIN DIRECT LOGIN — Email + PIN (no citizen login needed)
# ═══════════════════════════════════════════════════

@app.route("/api/admin/check-email")
def admin_check_email():
    """Check if an email belongs to an admin account and if PIN is set."""
    try:
        email = request.args.get("email","").lower().strip()
        if not email or "@" not in email:
            return jsonify({"is_admin": False, "error": "Invalid email."}), 400
        user = get_user_by_email(email)
        if not user:
            return jsonify({"is_admin": False, "error": "No account found with this email."}), 404
        if user.get("role") not in ("admin","authority"):
            return jsonify({"is_admin": False, "error": "This email does not have admin access."}), 403
        has_p = admin_has_pin(user["id"])
        return jsonify({"is_admin": True, "has_pin": has_p, "name": user.get("full_name","Admin")})
    except Exception as e:
        logger.error("check_email error: %s", e)
        return jsonify({"is_admin": False, "error": "Server error."}), 500

@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    """Admin-only login: email + PIN. Returns a JWT token if valid."""
    try:
        data  = request.get_json(silent=True) or {}
        email = (data.get("email") or "").lower().strip()
        pin   = str(data.get("pin") or "").strip()

        if not email or "@" not in email:
            return jsonify({"success": False, "error": "Enter a valid email address."}), 400
        if not pin or len(pin) < 4:
            return jsonify({"success": False, "error": "Enter your 4-digit PIN."}), 400

        # Get user from DB
        user = get_user_by_email(email)
        if not user:
            return jsonify({"success": False, "error": "No account found with this email."}), 404

        # Must be admin or authority
        if user.get("role") not in ("admin", "authority"):
            return jsonify({"success": False, "error": "This account does not have admin access."}), 403

        # Verify PIN
        if not verify_admin_pin(user["id"], pin):
            log_audit("ADMIN_LOGIN_FAIL", "user", str(user["id"]), user["id"], get_client_ip())
            return jsonify({"success": False, "error": "Incorrect PIN."}), 401

        # Issue token
        token = generate_token(user["id"], user["email"], user["full_name"], user["role"])
        update_last_login(user["id"])
        log_audit("ADMIN_LOGIN_OK", "user", str(user["id"]), user["id"], get_client_ip())
        return jsonify({
            "success": True,
            "token": token,
            "user": _safe_user(user)
        })

    except Exception as e:
        logger.error("admin_login error: %s", e, exc_info=True)
        return jsonify({"success": False, "error": "Server error. Try again."}), 500

# ── Errors ───────────────────────────────────────────────
@app.errorhandler(413)
def too_large(e): return jsonify({"error": "File too large. Max 10MB."}), 413
@app.errorhandler(404)
def not_found(e): return jsonify({"error": "Not found"}), 404
@app.errorhandler(500)
def server_err(e): logger.exception(e); return jsonify({"error": "Server error"}), 500

@app.after_request
def sec_headers(r):
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["X-Frame-Options"]        = "SAMEORIGIN"
    return r

if __name__ == "__main__":
    init_db()
    print("=" * 55)
    print("  SADAK AI v3 - National Road Intelligence")
    print("=" * 55)
    print("  App:     http://127.0.0.1:5000")
    print("  Admin:   http://127.0.0.1:5000/admin")
    print("  Scanner: http://127.0.0.1:5000/scanner")
    print("=" * 55)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)