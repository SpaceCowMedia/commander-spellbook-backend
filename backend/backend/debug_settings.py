from .settings import *  # noqa: F403, F401
from .settings import INSTALLED_APPS, TEMPLATES, MIDDLEWARE

ASYNC_GENERATION = False

assert 'django.contrib.admin' in INSTALLED_APPS, 'django.contrib.admin not in INSTALLED_APPS'
assert any(t.get('BACKEND') == 'django.template.backends.django.DjangoTemplates' and t.get('APP_DIRS') for t in TEMPLATES), 'No DjangoTemplates backend in TEMPLATES'

INSTALLED_APPS.append('debug_toolbar')
MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')
INTERNAL_IPS = ['127.0.0.1', 'localhost']
