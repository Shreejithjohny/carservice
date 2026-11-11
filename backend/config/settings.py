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

# Your domain(s), comma-separated. Render also tells the server its public hostname by itself.
CONFIGURED_HOSTS = [h.strip() for h in f"{os.getenv('ALLOWED_HOSTS', '')},{os.getenv('RENDER_EXTERNAL_HOSTNAME', '')}".split(",") if h.strip()]
ALLOWED_HOSTS = ["*"] if DEBUG else (CONFIGURED_HOSTS or ["localhost", "127.0.0.1", "testserver"])

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
    # Serves the built website (client/dist) and Django's static files straight from this server
    "whitenoise.middleware.WhiteNoiseMiddleware",
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

# Database: DATABASE_URL (what most hosts give you), else MySQL via USE_MYSQL + DB_*, else SQLite.
def database_from_url(url):
    """postgres://user:pass@host:5432/name or mysql://... -> a Django DATABASES entry."""
    from urllib.parse import parse_qs, unquote, urlsplit

    parts = urlsplit(url)
    engines = {"postgres": "postgresql", "postgresql": "postgresql", "mysql": "mysql"}
    if parts.scheme not in engines:
        raise ImproperlyConfigured("DATABASE_URL must start with postgres://, postgresql:// or mysql://")
    config = {
        "ENGINE": f"django.db.backends.{engines[parts.scheme]}",
        "NAME": unquote(parts.path.lstrip("/")),
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname or "",
        "PORT": str(parts.port or ""),
        # Reuse connections between requests instead of opening one per request
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
    options = {key: values[-1] for key, values in parse_qs(parts.query).items()}  # e.g. ?sslmode=require
    if engines[parts.scheme] == "mysql":
        options = {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'", **options}
    if options:
        config["OPTIONS"] = options
    return config


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_MYSQL = os.getenv("USE_MYSQL", "False").lower() in ("true", "1", "t")

if DATABASE_URL:
    DATABASES = {"default": database_from_url(DATABASE_URL)}
elif USE_MYSQL:
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

# The built website (npm run build -> client/dist). When that folder exists, this server also serves
# the website, so the whole product runs at one address: no CORS, one domain, one thing to host.
# Without it (local development with `npm run dev`) the backend serves only the API.
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST") or BASE_DIR.parent / "client" / "dist")
# On by default in production only; in development the website runs on its own port (npm run dev).
SERVE_FRONTEND = (
    os.getenv("SERVE_FRONTEND", str(not DEBUG)).lower() in ("true", "1", "t")
    and (FRONTEND_DIST / "index.html").is_file()
    and not TESTING
)
if SERVE_FRONTEND:
    WHITENOISE_ROOT = FRONTEND_DIST
# Vite puts a content hash in these file names, so browsers may cache them for a year
WHITENOISE_IMMUTABLE_FILE_TEST = lambda path, url: url.startswith("/assets/")  # noqa: E731
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# Public address of the React app; invoice QR codes link to its /verify page.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

# Uploaded photos and videos (car condition photos, repair evidence). On a host whose disk is wiped
# on every deploy, point MEDIA_ROOT at a persistent disk, or the uploads are lost.
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT") or BASE_DIR / "media")

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

# "Sign in with Google": the OAuth client ID from Google Cloud Console (APIs & Services >
# Credentials > OAuth client ID, type "Web application"). It is public, not a secret; the frontend
# reads it from /api/health-check/. Leave GOOGLE_CLIENT_ID unset or empty to use this project's own
# client; set it to another client ID to use yours, or to "off" to hide the Google button.
# (The client secret is not used anywhere and must never be put in the code or in .env.)
PROJECT_GOOGLE_CLIENT_ID = "491130655135-51cce4g7u58h5ubd3gem6v7pjoh1qqht.apps.googleusercontent.com"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip() or PROJECT_GOOGLE_CLIENT_ID
if GOOGLE_CLIENT_ID.lower() == "off":
    GOOGLE_CLIENT_ID = ""

# Demo mode: one-click role logins and the 123456 test codes for the driver pickup/delivery checks.
# Disabled by default; set OTP_BYPASS=true only in local/dev environments, never in production.
OTP_BYPASS = os.getenv("OTP_BYPASS", "False").lower() in ("true", "1", "t")

# Road routes on the Track page (OSRM). Empty = the free public demo server; set your own for heavy use.
ROUTING_URL = os.getenv("ROUTING_URL", "").strip()

# Online invoice payment: "mock" is a test gateway (no real money); empty disables online payment.
# "razorpay" takes real payments (UPI, cards, net banking) and needs the keys below.
PAYMENT_GATEWAY = os.getenv("PAYMENT_GATEWAY", "mock" if DEBUG else "").strip().lower()
# Razorpay Dashboard > Account & Settings > API keys. Test keys start with rzp_test_, live with rzp_live_.
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
# The secret you type when adding the webhook (<your API address>/api/payments/razorpay/webhook/)
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()

# Browser push notifications. Create the pair once with `python manage.py generate_vapid_keys`.
# Empty = no push; notifications still show inside the app.
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "").strip()
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "").strip()
# Contact address the push services (Google, Mozilla, Apple) can use if something misbehaves
VAPID_CONTACT_EMAIL = os.getenv("VAPID_CONTACT_EMAIL", "").strip() or "admin@smartdoorstep.com"


# Your business details, shown on the website's Privacy, Terms, Refunds and Contact pages.
# Payment providers such as Razorpay check those pages, so fill these in before going live.
BUSINESS = {
    "name": os.getenv("BUSINESS_NAME", "").strip() or "DoorStep",
    "legal_name": os.getenv("BUSINESS_LEGAL_NAME", "").strip(),  # registered name, as on GST or bank documents
    "address": os.getenv("BUSINESS_ADDRESS", "").strip(),
    "email": os.getenv("BUSINESS_EMAIL", "").strip(),
    "phone": os.getenv("BUSINESS_PHONE", "").strip(),
    "gstin": os.getenv("BUSINESS_GSTIN", "").strip(),  # optional
    "city": os.getenv("BUSINESS_CITY", "").strip(),  # whose courts handle disputes, e.g. Bengaluru
    "policies_updated": os.getenv("POLICIES_UPDATED", "").strip() or "11 November 2026",
}


# ---------------------------------------------------------------------------------------------
# Production safety. With DEBUG off the server refuses to start in a state that would be unsafe
# with real customers, and switches on the browser-side protections.
# ---------------------------------------------------------------------------------------------
def env_flag(name, default):
    return os.getenv(name, str(default)).lower() in ("true", "1", "t")


if not (DEBUG or TESTING):
    problems = []
    if OTP_BYPASS:
        problems.append("OTP_BYPASS is on: anyone could sign in to any account without a password. Set OTP_BYPASS=False.")
    if PAYMENT_GATEWAY == "mock":
        problems.append(
            "PAYMENT_GATEWAY=mock marks invoices paid without any money moving. Use PAYMENT_GATEWAY=razorpay, "
            "or leave it empty so customers pay at the service center."
        )
    if PAYMENT_GATEWAY == "razorpay" and not (RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET):
        problems.append("PAYMENT_GATEWAY=razorpay needs RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.")
    if PAYMENT_GATEWAY not in ("", "mock", "razorpay"):
        problems.append(f"Unknown PAYMENT_GATEWAY '{PAYMENT_GATEWAY}'. Use razorpay, or leave it empty.")
    if len(SECRET_KEY) < 32:
        problems.append("SECRET_KEY is too short. Use: python -c \"import secrets; print(secrets.token_urlsafe(50))\"")
    if not CONFIGURED_HOSTS:
        problems.append("ALLOWED_HOSTS is empty. Set it to your domain(s), e.g. ALLOWED_HOSTS=app.example.com")
    if DATABASES["default"]["ENGINE"].endswith("sqlite3") and not env_flag("ALLOW_SQLITE_IN_PRODUCTION", False):
        problems.append(
            "The database is SQLite, which loses data on hosts that wipe the disk and cannot protect time slots or "
            "coupons from being double-booked. Set DATABASE_URL (PostgreSQL or MySQL). To run a small demo on "
            "SQLite anyway, set ALLOW_SQLITE_IN_PRODUCTION=True."
        )
    if problems:
        raise ImproperlyConfigured("Unsafe production settings:\n- " + "\n- ".join(problems))

    # HTTPS everywhere. The host's proxy terminates TLS and tells us with X-Forwarded-Proto.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_flag("SECURE_SSL_REDIRECT", True)
    SECURE_REDIRECT_EXEMPT = [r"^api/health-check/$"]  # hosts check health over plain HTTP from inside
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", str(60 * 60 * 24 * 30)))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    # Lets the Django admin site's forms work behind the host's HTTPS proxy
    CSRF_TRUSTED_ORIGINS = [f"https://{host.lstrip('.')}" for host in ALLOWED_HOSTS if host not in ("*", "localhost", "127.0.0.1", "testserver")]
