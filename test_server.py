# test_server.py
import urllib.request
import urllib.error
import json

BASE = "http://127.0.0.1:8000"

def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=5) as r:
            return r.status, r.read().decode('utf-8')
    except Exception as e:
        return None, str(e)

def post(path, data):
    try:
        body = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(BASE + path, data=body,
                                     headers={'Content-Type': 'application/json'},
                                     method='POST')
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode('utf-8')
    except Exception as e:
        return None, str(e)

print("=" * 60)
print("تست سرور GCI")
print("=" * 60)

# تست ۱: health
print("\n[1] GET /health")
code, body = get("/health")
print("    Status:", code)
print("    Body:  ", body[:120])

# تست ۲: push
print("\n[2] POST /push")
payload = {
    "passphrase": "GCI_SECRET_2026",
    "ticker": "OANDA:XAUUSD",
    "bar_time_utc": "2026-07-13T14:30:00.000Z",
    "bS": 0, "buS": 1, "bH": 0, "buH": 1, "bA": 0, "buA": 0
}
code, body = post("/push", payload)
print("    Status:", code)
print("    Body:  ", body)

# تست ۳: poll (plain)
print("\n[3] GET /poll?format=plain&mark=0")
code, body = get("/poll?format=plain&mark=0")
print("    Status:", code)
print("    Body:  ", body if body else "(empty)")

# تست ۴: unacked
print("\n[4] GET /unacked (قبل از ack)")
code, body = get("/unacked")
print("    Status:", code)
print("    Body:  ", body[:200])

# تست ۵: ack
print("\n[5] GET /ack?ids=1")
code, body = get("/ack?ids=1")
print("    Status:", code)
print("    Body:  ", body)

# تست ۶: unacked بعد از ack
print("\n[6] GET /unacked (بعد از ack)")
code, body = get("/unacked")
print("    Status:", code)
print("    Body:  ", body[:200])

print("\n" + "=" * 60)
print("پایان تست")
print("=" * 60)
