from .production_settings import *  # noqa: F403, F401
from .production_settings import DATABASES

if DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql':
    DATABASES['default']['OPTIONS'] = {  # type: ignore
        'options': '-c statement_timeout=120000'  # in milliseconds
    }
