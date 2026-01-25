"""Django middleware for JWT cookie validation and admin allowlist enforcement.

Mirrors the authentication logic from the monolith:
  - backend/src/api/endpoints/auth.py (get_current_user — JWT cookie parsing)
  - backend/src/core/admin.py (require_admin — allowlist check, 404 response)

All requests except /healthz are gated. Non-admin users receive HTTP 404
(security through obscurity, matching monolith behavior).
"""

import logging

from django.conf import settings
from django.http import JsonResponse
from jose import JWTError, jwt

logger = logging.getLogger(__name__)

# Cache the parsed allowlist at module level
_admin_allowlist = None


def _get_admin_allowlist():
    """Parse ADMIN_ALLOWLIST setting into a set of lowercase usernames.

    Format: semicolon-separated usernames (e.g. 'alice;bob;charlie')
    Default: 'admina' if empty
    """
    global _admin_allowlist
    if _admin_allowlist is None:
        raw = getattr(settings, "ADMIN_ALLOWLIST", "") or ""
        if not raw.strip():
            raw = "admina"
        _admin_allowlist = {
            username.strip().lower()
            for username in raw.split(";")
            if username.strip()
        }
        logger.info(f"Admin allowlist loaded: {len(_admin_allowlist)} users")
    return _admin_allowlist


class AdminAllowlistMiddleware:
    """Django middleware that enforces admin-only access via JWT cookies.

    Skips /healthz (ungated for Kubernetes probes).
    Returns HTTP 404 for unauthenticated or non-admin users.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Allow /healthz without auth (K8s probes)
        if request.path == "/healthz" or request.path == "/healthz/":
            return self.get_response(request)

        # Extract JWT from access_token cookie
        token = request.COOKIES.get("access_token")
        if not token:
            return JsonResponse({"detail": "Not Found"}, status=404)

        # Strip 'Bearer ' prefix if present
        if token.startswith("Bearer "):
            token = token[7:]

        # Verify JWT
        try:
            secret_key = getattr(settings, "JWT_SECRET_KEY", "your-secret-key-here")
            algorithm = getattr(settings, "JWT_ALGORITHM", "HS256")
            payload = jwt.decode(token, secret_key, algorithms=[algorithm])
            username = payload.get("sub")
            if username is None:
                return JsonResponse({"detail": "Not Found"}, status=404)
        except JWTError:
            return JsonResponse({"detail": "Not Found"}, status=404)

        # Check admin allowlist
        allowlist = _get_admin_allowlist()
        if username.lower() not in allowlist:
            return JsonResponse({"detail": "Not Found"}, status=404)

        # Attach username to request for downstream use
        request.admin_username = username

        return self.get_response(request)
