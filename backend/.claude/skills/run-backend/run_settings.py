import os
import tempfile
from pathlib import Path
from backend.settings import *  # noqa: F401,F403

# Never the developer's db.sqlite3: a fresh file in the temp folder unless RUN_BACKEND_DB names another
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('RUN_BACKEND_DB') or str(Path(tempfile.gettempdir()) / 'spellbook-run-backend.sqlite3'),
    },
}
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']
# tasks run where they are enqueued, as in the tests: no worker to start
TASKS = {'default': {'BACKEND': 'django.tasks.backends.immediate.ImmediateBackend'}}
