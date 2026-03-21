"""
SADAK AI v3 - OTP Manager
Sends 6-digit OTP to user's email inbox via Gmail.
"""
import random, hashlib, logging, smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

SMTP_USER          = "darshanpaapani@gmail.com"
SMTP_PASS          = "duquxwxveibexbix"
OTP_EXPIRY_MINUTES = 10

_store = {}   # {email: {hash, expires, attempts}}


def send_otp(email: str) -> dict:
    email = email.lower().strip()
    otp   = str(random.randint(100000, 999999))

    _store[email] = {
        "hash":     _hash(otp, email),
        "expires":  datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES),
        "attempts": 0,
    }

    try:
        _send(email, otp)
        logger.info("OTP emailed to %s", email)
        return {"success": True, "message": f"OTP sent to {email}. Check your inbox."}
    except Exception as e:
        logger.error("Email failed for %s: %s", email, e)
        del _store[email]
        return {"success": False, "message": f"Email failed: {str(e)[:80]}. Try again."}


def verify_otp(email: str, otp: str):
    email = email.lower().strip()
    otp   = otp.strip()

    if email not in _store:
        return False, "No OTP found. Please click Send OTP first."

    r = _store[email]

    if datetime.now(timezone.utc) > r["expires"]:
        del _store[email]
        return False, "OTP expired. Please request a new one."

    if r["attempts"] >= 5:
        del _store[email]
        return False, "Too many wrong attempts. Request a new OTP."

    r["attempts"] += 1

    if _hash(otp, email) != r["hash"]:
        left = 5 - r["attempts"]
        return False, f"Wrong OTP. {left} attempt(s) left."

    del _store[email]
    return True, None


def _hash(otp, email):
    return hashlib.sha256(f"{otp}{email}SADAK2025".encode()).hexdigest()


def _send(to: str, otp: str):
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:40px 16px">
<table width="480" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb">

  <tr><td style="background:#0B3D91;padding:24px;text-align:center">
    <div style="color:#FF671F;font-size:24px;font-weight:900;letter-spacing:2px">SADAK<span style="color:#fff">AI</span></div>
    <div style="color:rgba(255,255,255,.5);font-size:10px;letter-spacing:3px;margin-top:4px;text-transform:uppercase">Smart Road Guardian</div>
  </td></tr>

  <tr><td style="padding:36px 32px;text-align:center">
    <p style="color:#111827;font-size:18px;font-weight:700;margin:0 0 8px">Email Verification</p>
    <p style="color:#6b7280;font-size:13px;margin:0 0 28px;line-height:1.6">
      Use the code below to complete your SADAK AI registration.
    </p>
    <div style="background:#f0f7ff;border:2px solid #bfdbfe;border-radius:12px;
                padding:24px 40px;display:inline-block;margin-bottom:24px">
      <div style="font-size:11px;font-weight:700;letter-spacing:2px;color:#3b82f6;
                  text-transform:uppercase;margin-bottom:10px">Your OTP Code</div>
      <div style="font-size:44px;font-weight:900;letter-spacing:16px;
                  color:#0B3D91;font-family:'Courier New',monospace">{otp}</div>
    </div>
    <p style="color:#6b7280;font-size:13px;margin:0 0 6px">
      Valid for <strong style="color:#111">{OTP_EXPIRY_MINUTES} minutes</strong> only.
    </p>
    <p style="color:#9ca3af;font-size:12px;margin:0">Never share this code with anyone.</p>
  </td></tr>

  <tr><td style="padding:0 32px 24px">
    <div style="background:#fffbeb;border:1px solid #fbbf24;border-radius:8px;padding:12px 16px;text-align:center">
      <p style="color:#92400e;font-size:12px;margin:0">
        &#9888; SADAK AI will <strong>never</strong> ask for this code over phone or chat.
        If you didn't request this, ignore this email.
      </p>
    </div>
  </td></tr>

  <tr><td style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:16px;text-align:center">
    <p style="color:#9ca3af;font-size:11px;margin:0">
      Government of India &bull; Ministry of Road Transport &amp; Highways
    </p>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = f"{otp} is your SADAK AI verification code"
    msg["From"]    = f"SADAK AI <{SMTP_USER}>"
    msg["To"]      = to
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as s:
        s.ehlo()
        s.starttls()
        s.ehlo()
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_USER, [to], msg.as_string())

# ── PASSWORD RESET ─────────────────────────────────────────
_reset_store = {}   # {email: {otp_hash, expires, attempts}}

def send_reset_otp(email: str) -> dict:
    """Send password reset OTP. Returns success/error — never reveals OTP."""
    email = email.lower().strip()
    otp   = str(random.randint(100000, 999999))

    _reset_store[email] = {
        "hash":     _hash(otp, email + "_RESET"),
        "expires":  datetime.now(timezone.utc) + timedelta(minutes=15),
        "attempts": 0,
    }

    try:
        _send_reset_email(email, otp)
        logger.info("Password reset OTP sent to %s", email)
        return {"success": True, "message": f"Password reset code sent to {email}. Check your inbox."}
    except Exception as e:
        logger.error("Reset email failed for %s: %s", email, e)
        del _reset_store[email]
        return {"success": False, "message": f"Could not send email: {str(e)[:60]}. Try again."}

def verify_reset_otp(email: str, otp: str) -> tuple:
    """Verify reset OTP. Returns (True, None) or (False, error_message)."""
    email = email.lower().strip()
    otp   = otp.strip()

    if email not in _reset_store:
        return False, "No reset code found. Please request a new one."

    r = _reset_store[email]

    if datetime.now(timezone.utc) > r["expires"]:
        del _reset_store[email]
        return False, "Reset code has expired. Please request a new one."

    if r["attempts"] >= 5:
        del _reset_store[email]
        return False, "Too many wrong attempts. Please request a new reset code."

    r["attempts"] += 1

    if _hash(otp, email + "_RESET") != r["hash"]:
        left = 5 - r["attempts"]
        return False, f"Incorrect code. {left} attempt(s) remaining."

    del _reset_store[email]
    return True, None

def _send_reset_email(to: str, otp: str):
    """Send professional password reset email."""
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:40px 16px">
<table width="480" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb">
  <tr><td style="background:#0B3D91;padding:24px;text-align:center">
    <div style="color:#FF671F;font-size:24px;font-weight:900;letter-spacing:2px">SADAK<span style="color:#fff">AI</span></div>
    <div style="color:rgba(255,255,255,.5);font-size:10px;letter-spacing:3px;margin-top:4px;text-transform:uppercase">Smart Road Guardian</div>
  </td></tr>
  <tr><td style="padding:32px 24px;text-align:center">
    <div style="width:52px;height:52px;background:#fff3ee;border-radius:50%;margin:0 auto 16px;line-height:52px;font-size:22px;text-align:center">🔐</div>
    <p style="color:#111827;font-size:17px;font-weight:700;margin:0 0 8px">Password Reset Request</p>
    <p style="color:#6b7280;font-size:13px;margin:0 0 24px;line-height:1.6">
      We received a request to reset your SADAK AI password.<br>
      Use the code below to set a new password.
    </p>
    <div style="background:#f0f7ff;border:2px solid #bfdbfe;border-radius:12px;padding:20px 32px;margin-bottom:20px">
      <div style="font-size:11px;font-weight:700;letter-spacing:2px;color:#3b82f6;text-transform:uppercase;margin-bottom:8px">Reset Code</div>
      <div style="font-size:40px;font-weight:900;letter-spacing:14px;color:#0B3D91;font-family:'Courier New',monospace">{otp}</div>
    </div>
    <p style="color:#6b7280;font-size:12px;margin:0 0 6px">Valid for <strong style="color:#111">15 minutes</strong> only.</p>
    <p style="color:#9ca3af;font-size:12px;margin:0">If you did not request this, your account is safe — ignore this email.</p>
  </td></tr>
  <tr><td style="background:#fef9ee;border-top:1px solid #fde68a;padding:12px 24px;text-align:center">
    <p style="color:#92400e;font-size:11px;margin:0">&#9888; SADAK AI will never ask for this code over phone or chat.</p>
  </td></tr>
  <tr><td style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:14px;text-align:center">
    <p style="color:#9ca3af;font-size:11px;margin:0">Government of India &bull; Ministry of Road Transport &amp; Highways</p>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = f"{otp} — SADAK AI Password Reset Code"
    msg["From"]    = f"SADAK AI <{SMTP_USER}>"
    msg["To"]      = to
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as s:
        s.ehlo(); s.starttls(); s.ehlo()
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_USER, [to], msg.as_string())