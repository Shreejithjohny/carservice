from django.contrib import admin
from django.http import FileResponse, JsonResponse
from django.urls import include, path, re_path
from django.conf import settings
from django.views.static import serve
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


def website(request):
    """
    Any address that is not the API: the React app, which then shows the right page itself
    (/app/track, /login/driver, ...). Only used when the built website is present.
    """
    response = FileResponse(open(settings.FRONTEND_DIST / "index.html", "rb"), content_type="text/html")
    response["Cache-Control"] = "no-cache"  # always the latest build; the hashed assets are cached instead
    return response


urlpatterns = [
    path('favicon.ico', favicon, name='favicon'),
    # The Django admin site (database tables: users, coupons, service packages). Not at /admin/,
    # because that address belongs to the website's admin area.
    path('django-admin/', admin.site.urls),
    path('api/', include('api.urls')),
    # Uploaded photos and videos
    re_path(r'^media/(?P<path>.*)$', require_safe(serve), {'document_root': settings.MEDIA_ROOT}),
]

if settings.SERVE_FRONTEND:
    urlpatterns += [re_path(r'^(?!api/|django-admin/|media/|static/).*$', require_safe(website), name='website')]
else:
    urlpatterns += [path('', api_root, name='api_root')]
