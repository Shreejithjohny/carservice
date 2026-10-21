import os
import sys
from pathlib import Path
from datetime import timedelta
import dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"

# Load environment variables from .env file. Tests skip it so they behave the same on every
# machine and never use real SMS/email credentials from a developer's .env.
if not TESTING:
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
            "NAME": BASE_DIR / "db.sqlite3",
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
EMAIL_HOST = os.getenv("EMAIL_HOST", "").strip()
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in ("true", "1", "t")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL") or "noreply@smartdoorstep.com"

# OTP Verification Mode: disabled by default for secure production behavior.
# Set OTP_BYPASS=true only in local/dev environments when debug bypass codes are intentionally enabled.
OTP_BYPASS = os.getenv("OTP_BYPASS", "False").lower() in ("true", "1", "t")

# When no SMS/email provider is configured, print OTPs to the server console instead of failing.
# On by default only in DEBUG; in production a missing provider is reported as an error.
OTP_CONSOLE_FALLBACK = os.getenv("OTP_CONSOLE_FALLBACK", str(DEBUG)).lower() in ("true", "1", "t")

# Online invoice payment: "mock" is a test gateway (no real money); empty disables online payment.
PAYMENT_GATEWAY = os.getenv("PAYMENT_GATEWAY", "mock" if DEBUG else "").strip().lower()

