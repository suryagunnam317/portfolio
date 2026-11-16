import os, re, json, sqlite3, urllib.request
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)
SQLITE_PATH = os.path.join("/tmp" if os.environ.get("VERCEL") else ".", "portfolio.db")


# ---------- Supabase (used on Vercel) ----------
def sb(method, path, body=None, extra=None):
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
               "Content-Type": "application/json"}
    headers.update(extra or {})
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", data=data,
                                 headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.headers.get("Content-Range", "")


# ---------- SQLite (local fallback) ----------
def lite():
    db = sqlite3.connect(SQLITE_PATH)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, email TEXT, message TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS visits(id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT);
    """)
    return db


def now():
    return datetime.now(timezone.utc).isoformat()


def record_visit():
    """Add one visit and return the total."""
    try:
        if USE_SUPABASE:
            sb("POST", "visits", {}, {"Prefer": "return=minimal"})
            rng = sb("GET", "visits?select=id&limit=1", extra={"Prefer": "count=exact"})
            return int(rng.split("/")[-1])
        db = lite()
        db.execute("INSERT INTO visits(created_at) VALUES(?)", (now(),))
        db.commit()
        return db.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
    except Exception as e:
        app.logger.error("visit counter failed: %s", e)
        return "—"


def save_message(name, email, message):
    if USE_SUPABASE:
        sb("POST", "messages", {"name": name, "email": email, "message": message},
           {"Prefer": "return=minimal"})
    else:
        db = lite()
        db.execute("INSERT INTO messages(name,email,message,created_at) VALUES(?,?,?,?)",
                   (name, email, message, now()))
        db.commit()


@app.route("/")
def home():
    return render_template("index.html", visits=record_visit())


@app.post("/api/contact")
def contact():
    d = request.get_json(silent=True) or {}
    name = (d.get("name") or "").strip()
    email = (d.get("email") or "").strip()
    message = (d.get("message") or "").strip()
    if not name or len(name) > 80:
        return jsonify(ok=False, error="Enter your name (up to 80 characters)."), 400
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify(ok=False, error="Enter a valid email address."), 400
    if not 5 <= len(message) <= 1000:
        return jsonify(ok=False, error="Message must be 5 to 1000 characters."), 400
    try:
        save_message(name, email, message)
    except Exception as e:
        app.logger.error("save failed: %s", e)
        return jsonify(ok=False, error="Could not save your message. Try again later."), 500
    return jsonify(ok=True, message="Thanks, your message was sent.")


if __name__ == "__main__":
    app.run(debug=True)
