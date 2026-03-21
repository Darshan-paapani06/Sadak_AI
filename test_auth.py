import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=== SADAK AI Auth Test ===")

# Step 1: Check PyJWT
try:
    import jwt
    print("PyJWT version:", jwt.__version__)
    print("PyJWT location:", jwt.__file__)
except Exception as e:
    print("ERROR importing jwt:", e)
    sys.exit(1)

# Step 2: Raw JWT test
KEY = "SADAK2025IndiaRoadGuardian_FixedKey_XyZ"
from datetime import datetime, timezone, timedelta
now = datetime.now(timezone.utc)
payload = {
    "sub": 1, "email": "test@test.com", "name": "Test", "role": "citizen",
    "iat": int(now.timestamp()),
    "exp": int((now + timedelta(days=30)).timestamp()),
}
try:
    token = jwt.encode(payload, KEY, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    print("Token generated OK:", token[:40])
except Exception as e:
    print("ERROR generating token:", e)
    sys.exit(1)

# Step 3: Decode attempts
decoded = None
try:
    decoded = jwt.decode(token, KEY, algorithms=["HS256"])
    print("Decode attempt 1 (algorithms list): OK")
except Exception as e:
    print("Decode attempt 1 failed:", e)
    try:
        decoded = jwt.decode(token, KEY, algorithm="HS256")
        print("Decode attempt 2 (algorithm single): OK")
    except Exception as e2:
        print("Decode attempt 2 failed:", e2)

if decoded:
    print("Email:", decoded.get("email"))
    print("")
    print("ALL TESTS PASSED — login will work!")
else:
    print("")
    print("JWT decode failing — fixing with pip:")
    print("Run: pip install --upgrade PyJWT --user")