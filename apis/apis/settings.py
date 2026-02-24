import os
from datetime import timedelta
from pathlib import Path
import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

ENV = environ.Env()
DEBUG = ENV("DEBUG")

ALLOWED_HOSTS = ["cryphos.com"]


SUPPORTED_TIMEFRAMES = {
    "1m": "1MIN",
    "5m": "5MIN",
    "15m": "15MIN",
    "30m": "30MIN",
    "1h": "1HRS",
    "1d": "1DAY",
}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "accounts",
    "assets",
    "bots",
    "core",
    "celery",
    "redis",
    "channels",
    "drf_spectacular",
]

SPECTACULAR_SETTINGS = {
    "TITLE": "Cryphos API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SECURITY": [{"BearerAuth": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
}
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

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

AUTH_USER_MODEL = "accounts.User"
APPEND_SLASH = False


STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]


CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "http-user-data",
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_PREFLIGHT_MAX_AGE = 86400

ROOT_URLCONF = "apis.urls"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(os.getenv("REDIS_HOST", "redis"), int(os.getenv("REDIS_PORT", "6379")))],
        },
    },
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "apis.wsgi.application"
ASGI_APPLICATION = "apis.asgi.application"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://redis:6379/1",
    }
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "cryphos",
        "USER": "cryphos_user",
        "PASSWORD": ENV("DB_PASSWORD"),
        "HOST": ENV("DB_HOST"),
        "PORT": "5432",
        "OPTIONS": {
            "pool": True,
        },
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "en-us"

CELERY_BROKER_URL = "redis://redis:6379/0"
CELERY_RESULT_BACKEND = "redis://redis:6379/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
TIME_ZONE = "Europe/Berlin"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

TELEGRAM_BOT_TOKEN = ENV("TELEGRAM_BOT_TOKEN")


CSRF_TRUSTED_ORIGINS = [
    "https://cryphos.com",
]
CORS_ALLOWED_ORIGINS = ["https://cryphos.com"]


if DEBUG:
    CSRF_TRUSTED_ORIGINS += ["http://localhost:3000", "http://127.0.0.1:3000"]
    ALLOWED_HOSTS += ["127.0.0.1", "localhost"]
    CORS_ALLOWED_ORIGINS += [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

FRONTEND_URL = ENV("FRONTEND_URL")
SECRET_KEY = ENV("SECRET_KEY")
STRIPE_SECRET_KEY = ENV("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = ENV("STRIPE_WEBHOOK_SECRET")
STRIPE_PRICE_ID = ENV("STRIPE_PRICE_ID")

EMAIL_BACKEND = ENV("EMAIL_BACKEND")
EMAIL_HOST = ENV("EMAIL_HOST")
EMAIL_PORT = ENV("EMAIL_PORT")
EMAIL_HOST_USER = ENV("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = "$(6.WD!qs=dYG)z"
EMAIL_USE_TLS = ENV("EMAIL_USE_TLS")
EMAIL_USE_SSL = ENV("EMAIL_USE_SSL")
EMAIL_TIMEOUT = ENV("EMAIL_TIMEOUT")
DEFAULT_FROM_EMAIL = ENV("DEFAULT_FROM_EMAIL")

CELERY_BEAT_SCHEDULE = {
    "fetch-1m": {
        "task": "core.tasks.fetch_ohlcv_for_interval",
        "schedule": crontab(),
        "args": ("1m",),
    },
    "fetch-5m": {
        "task": "core.tasks.fetch_ohlcv_for_interval",
        "schedule": crontab(minute="*/5"),
        "args": ("5m",),
    },
    "fetch-15m": {
        "task": "core.tasks.fetch_ohlcv_for_interval",
        "schedule": crontab(minute="*/15"),
        "args": ("15m",),
    },
    "fetch-30m": {
        "task": "core.tasks.fetch_ohlcv_for_interval",
        "schedule": crontab(minute="*/30"),
        "args": ("30m",),
    },
    "fetch-1h": {
        "task": "core.tasks.fetch_ohlcv_for_interval",
        "schedule": crontab(minute=0),
        "args": ("1h",),
    },
    "fetch-1d": {
        "task": "core.tasks.fetch_ohlcv_for_interval",
        "schedule": crontab(hour=0, minute=0),
        "args": ("1d",),
    },
    "calculate-signals": {
        "task": "core.tasks.calculate_signals",
        "schedule": timedelta(seconds=5),
    },
    "calculate-swing": {
        "task": "core.tasks.calculate_swing",
        "schedule": timedelta(seconds=5),
    },
    "check_roi": {
        "task": "core.tasks.check_roi",
        "schedule": timedelta(seconds=5),
    },
    "parse_fng": {
        "task": "core.tasks.parse_fng",
        "schedule": crontab(hour=0, minute=0),
    },
    "parse_funding_rate": {
        "task": "core.tasks.parse_funding_rate",
        "schedule": crontab(hour="0,8,16", minute=5),
    },
}
