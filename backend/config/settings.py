import os
import sys
from pathlib import Path
from datetime import timedelta
import dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"

# Load environment variables from .env file. Tests (and the browser tests, via IGNORE_DOTENV) skip it
# so they behave the same on every machine and never use real SMS/email credentials from a developer's .env.
if not TESTING and not os.getenv("IGNORE_DOTENV"):
    dotenv.load_dotenv(BASE_DIR / ".env")

# Production-safe defaults: DEBUG is off unless explicitly enabled (backend/.env.example turns it on for local dev).
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY:
    if not (DEBUG or TESTING):
        raise ImproperlyConfigured(
            "SECRET_KEY must be set when DEBUG is off. Copy backend/.env.example to backend/.env for local development."
        )
    SECRET_KEY = "django-insecure-local-development-only-key"
elif SECRET_KEY.startswith("django-insecure") and not (DEBUG or TESTING):
    raise ImproperlyConfigured("Replace the placeholder SECRET_KEY with a long random value before running with DEBUG off.")

ALLOWED_HOSTS = ["*"] if DEBUG else [h.strip() for h in (os.getenv("ALLOWED_HOSTS") or "localhost,127.0.0.1,testserver").split(",") if h.strip()]

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third party apps
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",

    # Local apps
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database Configuration (MySQL with SQLite fallback)
USE_MYSQL = os.getenv("USE_MYSQL", "False").lower() in ("true", "1", "t")

if USE_MYSQL:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "smart_doorstep_db"),
            "USER": os.getenv("DB_USER", "root"),
            "PASSWORD": os.getenv("DB_PASSWORD", "root"),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            # SQLITE_PATH lets the browser tests use their own throwaway database
            "NAME": os.getenv("SQLITE_PATH") or BASE_DIR / "db.sqlite3",
        }
    }

# Custom User Model
AUTH_USER_MODEL = "api.User"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# Static & Media Files
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Public address of the React app; invoice QR codes link to its /verify page.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS Configuration: any origin in development, only listed origins otherwise.
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
CORS_ALLOW_CREDENTIALS = True

# REST Framework Settings
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    # Number of reverse proxies in front of Django (e.g. 1 behind Nginx or a hosting load balancer),
    # used to find the caller's real IP for the OTP rate limits. 0 = use the connection's address and
    # ignore X-Forwarded-For, which a client could fake. Set it to match your hosting, not higher.
    "NUM_PROXIES": int(os.getenv("NUM_PROXIES", "0")),
}

# Simple JWT Settings
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_EXPIRATION_MINUTES", 60))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_EXPIRATION_DAYS", 7))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Email delivery for OTPs (used when EMAIL_HOST is set)
# (`python manage.py check_email you@example.com` sends a test email and explains any error.)
EMAIL_HOST = os.getenv("EMAIL_HOST", "").strip()
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "").strip()
if EMAIL_HOST.lower() == "smtp.gmail.com":
    # Google shows App Passwords as "abcd efgh ijkl mnop"; Gmail needs them without the spaces
    EMAIL_HOST_PASSWORD = EMAIL_HOST_PASSWORD.replace(" ", "")
# Port 465 speaks SSL from the first byte; 587 (and most others) start plain and switch with STARTTLS.
# Django refuses both at once, so 465 turns TLS off unless EMAIL_USE_SSL/EMAIL_USE_TLS say otherwise.
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", str(EMAIL_PORT == 465)).lower() in ("true", "1", "t")
EMAIL_USE_TLS = (not EMAIL_USE_SSL) and os.getenv("EMAIL_USE_TLS", "True").lower() in ("true", "1", "t")
# Most providers (Gmail included) only send From the signed-in address or a verified sender, so
# default to the login address rather than a made-up one that could be rejected or sent to spam.
DEFAULT_FROM_EMAIL = (
    os.getenv("DEFAULT_FROM_EMAIL", "").strip()
    or (EMAIL_HOST_USER if "@" in EMAIL_HOST_USER else "")
    or "noreply@smartdoorstep.com"
)
# Seconds to wait for the mail server before giving up (so a stuck SMTP server can't hang requests)
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))

# OTP rate limits (see api/otp_rate_limit.py). They protect the SMS/email bill and stop code guessing.
# Not applied when OTP_BYPASS is on. Set a limit to 0 to switch it off.
OTP_SEND_LIMIT_PER_IDENTIFIER = int(os.getenv("OTP_SEND_LIMIT_PER_IDENTIFIER", "5"))  # per email/number per hour
OTP_SEND_LIMIT_PER_IP = int(os.getenv("OTP_SEND_LIMIT_PER_IP", "10"))  # per IP address per hour
OTP_SEND_DAILY_LIMIT = int(os.getenv("OTP_SEND_DAILY_LIMIT", "400"))  # whole server per 24 h (Gmail allows ~500/day)
OTP_VERIFY_LIMIT_PER_IP = int(os.getenv("OTP_VERIFY_LIMIT_PER_IP", "30"))  # code checks per IP address per hour

# OTP Verification Mode: disabled by default for secure production behavior.
# Set OTP_BYPASS=true only in local/dev environments when debug bypass codes are intentionally enabled.
OTP_BYPASS = os.getenv("OTP_BYPASS", "False").lower() in ("true", "1", "t")

# Road routes on the Track page (OSRM). Empty = the free public demo server; set your own for heavy use.
ROUTING_URL = os.getenv("ROUTING_URL", "").strip()

# When no SMS/email provider is configured, print OTPs to the server console instead of failing.
# On by default only in DEBUG; in production a missing provider is reported as an error.
OTP_CONSOLE_FALLBACK = os.getenv("OTP_CONSOLE_FALLBACK", str(DEBUG)).lower() in ("true", "1", "t")

# Online invoice payment: "mock" is a test gateway (no real money); empty disables online payment.
PAYMENT_GATEWAY = os.getenv("PAYMENT_GATEWAY", "mock" if DEBUG else "").strip().lower()

