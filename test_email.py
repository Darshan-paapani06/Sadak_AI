"""
Run this to test if Gmail is working:
  python test_email.py
"""
import smtplib, sys, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── PUT YOUR NEW APP PASSWORD HERE ───────────────────────
SMTP_USER = "darshanpaapani@gmail.com"
SMTP_PASS = "duquxwxveibexbix"   # ← PASTE YOUR NEW 16-CHAR PASSWORD HERE (no spaces)
TEST_TO   = "darshanpaapani@gmail.com"   # send test to yourself
# ─────────────────────────────────────────────────────────

if not SMTP_PASS.strip():
    print("\nERROR: SMTP_PASS is empty!")
    print("Open this file and paste your new App Password.")
    input("Press Enter..."); sys.exit(1)

print(f"\nTesting Gmail: {SMTP_USER}")
print(f"App Password:  {SMTP_PASS[:4]}...{SMTP_PASS[-4:]}")
print(f"Sending to:    {TEST_TO}\n")

try:
    print("Connecting to smtp.gmail.com:587...")
    srv = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
    srv.ehlo()
    print("EHLO: OK")
    srv.starttls()
    print("STARTTLS: OK")
    srv.ehlo()
    srv.login(SMTP_USER, SMTP_PASS)
    print("LOGIN: OK  ✓")

    # Send test email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "SADAK AI — Email Test"
    msg["From"]    = f"SADAK AI <{SMTP_USER}>"
    msg["To"]      = TEST_TO
    msg.attach(MIMEText("""
    <div style="font-family:Arial;padding:20px;background:#0B3D91;color:white;text-align:center;border-radius:8px">
        <h2 style="color:#FF671F">SADAK AI</h2>
        <p>Email is working correctly!</p>
        <p style="font-size:12px;opacity:.7">This is a test from your SADAK AI app.</p>
    </div>
    """, "html"))
    srv.sendmail(SMTP_USER, [TEST_TO], msg.as_string())
    srv.quit()
    print(f"\n✅ SUCCESS! Test email sent to {TEST_TO}")
    print("Check your inbox (and spam folder).")
    print("\nNow update SMTP_PASS in otp_manager.py with the same password.")

except smtplib.SMTPAuthenticationError as e:
    print(f"\n❌ AUTH FAILED: {e}")
    print("\nFixes to try:")
    print("1. Delete the App Password and create a new one")
    print("2. Make sure 2-Step Verification is ON")
    print("3. Copy the password WITHOUT spaces")

except Exception as e:
    print(f"\n❌ Error: {e}")

input("\nPress Enter to exit...")