'''manage.py for an agent: the same commands on a database of its own, whatever the platform.

It puts the backend, the shared `common` package and this directory on the path, so no PYTHONPATH
(`;` on Windows, `:` elsewhere) is needed, and uses run_settings, whose database is RUN_BACKEND_DB.
`seed` is a command of its own: a superuser and a small combo whose rows carry dictionaries.
'''
import os
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent
BACKEND = SKILL.parents[2]
sys.path[:0] = [str(BACKEND), str(BACKEND.parent / 'common'), str(SKILL)]
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'run_settings')

if __name__ == '__main__':
    if sys.argv[1:2] == ['seed']:
        import django
        django.setup()
        from seed import seed
        seed()
    else:
        from django.core.management import execute_from_command_line
        execute_from_command_line(sys.argv)
