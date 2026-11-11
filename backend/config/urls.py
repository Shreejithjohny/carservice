from django.contrib import admin
from django.http import FileResponse, JsonResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.decorators.http import require_safe


@require_safe
def api_root(request):
    return JsonResponse({
        "message": "Smart Doorstep API is running.",
        "status": "ok",
        "routes": ["/api/health-check/", "/api/auth/login/", "/api/auth/google/"],
    })


@require_safe
def favicon(request):
    """The logo for browser tabs showing backend pages (the API root, the Django admin, invoice PDFs)."""
    response = FileResponse(open(settings.BASE_DIR / "api" / "assets" / "favicon.ico", "rb"), content_type="image/x-icon")
    response["Cache-Control"] = "public, max-age=86400"
    return response


urlpatterns = [
    path('', api_root, name='api_root'),
    path('favicon.ico', favicon, name='favicon'),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
