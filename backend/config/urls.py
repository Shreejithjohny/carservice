from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


def api_root(request):
    return JsonResponse({
        "message": "Smart Doorstep API is running.",
        "status": "ok",
        "routes": ["/api/health-check/", "/api/auth/send-otp/", "/api/auth/verify-otp/"],
    })


urlpatterns = [
    path('', api_root, name='api_root'),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
