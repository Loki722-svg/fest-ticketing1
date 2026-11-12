"""Admin login using signed tokens (standard library only, no extra packages)."""
import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Header, HTTPException

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
TOKEN_TTL = 8 * 3600  # 8 hours


def _sign(payload: str) -> str:
    return hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


def check_credentials(username: str, password: str) -> bool:
    ok_user = hmac.compare_digest(username.encode(), ADMIN_USER.encode())
    ok_pass = hmac.compare_digest(password.encode(), ADMIN_PASSWORD.encode())
    return ok_user and ok_pass


def create_token(username: str) -> str:
    data = {"u": username, "exp": int(time.time()) + TOKEN_TTL}
    payload = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str) -> bool:
    try:
        payload, sig = token.split(".", 1)
        if not hmac.compare_digest(sig, _sign(payload)):
            return False
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
        return data["exp"] > time.time()
    except Exception:
        return False


def require_admin(authorization: str = Header(default="")):
    """Dependency: put on any route that only the admin may use."""
    token = authorization.removeprefix("Bearer ").strip()
    if not token or not verify_token(token):
        raise HTTPException(401, "Admin login required")
