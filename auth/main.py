import os
import datetime

import jwt
from flask import Flask, request, jsonify, redirect, render_template_string

app = Flask(__name__)

AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "password123")
JWT_SECRET    = os.environ.get("JWT_SECRET", "dev-secret-change-me")
API_URL       = os.environ.get("API_URL", "http://localhost:5001")

LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
  <title>snaPDF — Sign In</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: sans-serif; max-width: 400px; margin: 120px auto; padding: 0 24px; color: #222; }
    h1 { font-size: 1.6rem; margin-bottom: 4px; }
    .sub { color: #666; margin-bottom: 32px; font-size: 0.95rem; }
    label { display: block; font-weight: 600; margin-bottom: 6px; }
    input { display: block; width: 100%; padding: 9px 12px; border: 1px solid #ccc; margin-bottom: 20px; font-size: 0.95rem; }
    button { width: 100%; padding: 11px; background: #1a56db; color: #fff; border: none; font-size: 1rem; cursor: pointer; }
    .error { color: #c0392b; margin-bottom: 16px; font-size: 0.9rem; }
    .hint { text-align: center; margin-top: 20px; font-size: 0.9rem; color: #666; }
    .hint a { color: #1a56db; }
  </style>
</head>
<body>
  <h1>snaPDF</h1>
  <p class="sub">Sign in for priority queue access.</p>
  {% if error %}<p class="error">{{ error }}</p>{% endif %}
  <form method="POST" action="/login">
    <label>Username</label>
    <input type="text" name="username" required autofocus>
    <label>Password</label>
    <input type="password" name="password" required>
    <button type="submit">Sign In</button>
  </form>
  <p class="hint">No account? <a href="{{ api_url }}">Use free tier →</a></p>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(LOGIN_PAGE, error=None, api_url=API_URL)


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if username != AUTH_USERNAME or password != AUTH_PASSWORD:
        return render_template_string(LOGIN_PAGE, error="Invalid username or password.", api_url=API_URL), 401

    token = jwt.encode(
        {
            "sub": username,
            "tier": "signed",
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8),
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    # Redirect to the API with token in the URL — the API page picks it up automatically
    return redirect(f"{API_URL}?token={token}")


@app.route("/verify", methods=["POST"])
def verify():
    """Called by the API service to validate a JWT and return the user's tier."""
    data = request.get_json(silent=True) or {}
    token = data.get("token", "")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return jsonify({"valid": True, "username": payload["sub"], "tier": payload.get("tier", "free")})
    except jwt.ExpiredSignatureError:
        return jsonify({"valid": False, "error": "token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"valid": False, "error": "invalid token"}), 401


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
