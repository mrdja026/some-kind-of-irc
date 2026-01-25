"""
URL configuration for data-processor service.

Routes all API requests to the api app.
/healthz is an ungated endpoint for Kubernetes probes (bypasses JWT middleware).
"""

from django.http import JsonResponse
from django.urls import path, include


def healthz(request):
    """Kubernetes liveness/readiness probe (no auth required).

    This endpoint is whitelisted in the AdminAllowlistMiddleware
    so it does not require a valid JWT cookie.
    """
    return JsonResponse({"service": "data-processor", "status": "ok"})


urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("api/", include("api.urls")),
]
