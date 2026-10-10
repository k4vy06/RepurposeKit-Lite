"""
Security utilities:
- CSRF token generation and validation
- Session middleware configuration
- Security headers middleware
"""
import os
import secrets
from fastapi import Request, HTTPException
from starlette.middleware.sessions import SessionMiddleware

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
CSRF_TOKEN_KEY = "csrf_token"


def get_or_create_csrf_token(request: Request) -> str:
    """Return existing CSRF token from session, or generate and store a new one."""
    token = request.session.get(CSRF_TOKEN_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_TOKEN_KEY] = token
    return token


def validate_csrf_token(request: Request, submitted_token: str) -> None:
    """Raise HTTP 403 if the submitted CSRF token does not match the session token."""
    session_token = request.session.get(CSRF_TOKEN_KEY)
    if not session_token or not secrets.compare_digest(session_token, submitted_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token.")


SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self';"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}
