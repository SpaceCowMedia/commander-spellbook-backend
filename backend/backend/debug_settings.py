import os
from .settings import *  # noqa: F403, F401
from .settings import INSTALLED_APPS, TEMPLATES, MIDDLEWARE, DATABASES

assert 'django.contrib.admin' in INSTALLED_APPS, 'django.contrib.admin not in INSTALLED_APPS'
assert any(t.get('BACKEND') == 'django.template.backends.django.DjangoTemplates' and t.get('APP_DIRS') for t in TEMPLATES), 'No DjangoTemplates backend in TEMPLATES'

INSTALLED_APPS.append('debug_toolbar')
MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')
INTERNAL_IPS = ['127.0.0.1', 'localhost']

if os.getenv('SQL_ENGINE', DATABASES['default']['ENGINE']) != DATABASES['default']['ENGINE']:
    DATABASES = {
        'default': {
            'OPTIONS': {
                'options': '-c statement_timeout=60000'  # in milliseconds
            },
            'ENGINE': os.getenv('SQL_ENGINE'),
            'NAME': os.environ.get('SQL_DATABASE', DATABASES['default']['NAME']),
            'USER': os.environ.get('SQL_USER', 'user'),
            'PASSWORD': os.environ.get('SQL_PASSWORD', 'password'),
            'HOST': os.environ.get('SQL_HOST', 'localhost'),
            'PORT': os.environ.get('SQL_PORT', '5432'),
        }
    }

if DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql':
    INSTALLED_APPS.append('django.contrib.postgres')
