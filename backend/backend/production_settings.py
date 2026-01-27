import os
from .settings import *  # noqa: F403, F401
from .settings import BASE_DIR, INSTALLED_APPS
from urllib.parse import urlparse

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Security settings

CSRF_TRUSTED_ORIGINS = [
    'https://*.commanderspellbook.com',
    'http://localhost',
    'http://127.0.0.1',
    'http://localhost:3000',
    'http://web:8000',
]

ALLOWED_HOSTS = [hostname.removeprefix('*') for hostname in (urlparse(origin).hostname for origin in CSRF_TRUSTED_ORIGINS) if hostname is not None]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^https://(\w+\.)?commanderspellbook\.com$',
    r'https?://localhost:\d+',
]

SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS = [
    'commanderspellbook.com',
    'dev.commanderspellbook.com',
    'localhost:3000',
]

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# Reverse proxy settings
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Pod settings
POD_IP = os.getenv('THIS_POD_IP', None)
if POD_IP is not None:
    ALLOWED_HOSTS.append(POD_IP)

# Production settings
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_BULK_FOLDER = STATIC_ROOT / 'bulk'
CONN_MAX_AGE = 60 * 60

# Database
# https://docs.djangoproject.com/en/dev/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': os.getenv('SQL_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': os.getenv('SQL_DATABASE', os.path.join(BASE_DIR, 'db.sqlite3')),
        'USER': os.getenv('SQL_USER', 'user'),
        'PASSWORD': os.getenv('SQL_PASSWORD', 'password'),
        'HOST': os.getenv('SQL_HOST', 'localhost'),
        'PORT': os.getenv('SQL_PORT', '5432'),
    }
}

if DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql':
    INSTALLED_APPS.append('django.contrib.postgres')
    DATABASES['default']['OPTIONS'] = {  # type: ignore
        'options': '-c statement_timeout=60000'  # in milliseconds
    }

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
