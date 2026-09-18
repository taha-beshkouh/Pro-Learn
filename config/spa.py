from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.views.decorators.http import require_safe


@require_safe
def spa_index(request):
    """Serve the generated Vite entry point for browser-owned routes only."""
    index_path = Path(settings.FRONTEND_DIST_DIR) / "index.html"
    if not index_path.is_file():
        raise ImproperlyConfigured(
            "Frontend production build is missing. Run npm ci and npm run build "
            "from frontend/ before starting the combined application."
        )

    response = HttpResponse(index_path.read_bytes(), content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    return response
