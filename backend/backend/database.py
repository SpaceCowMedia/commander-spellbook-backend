from contextvars import ContextVar
from functools import lru_cache
from django.conf import settings
from django.db import DEFAULT_DB_ALIAS
from django.urls import reverse

ADMIN_DATABASE = 'admin'
# The middleware sets this on every request, so the default is what code running outside one gets. It has to stay on the default alias:
# migrations run their data changes through the ORM, and routing those to a second connection puts them outside the transaction holding the schema changes.
current_database_var: ContextVar[str] = ContextVar('current_database', default=DEFAULT_DB_ALIAS)


def current_database() -> str:
    database = current_database_var.get()
    return database if database in settings.DATABASES else DEFAULT_DB_ALIAS


@lru_cache(maxsize=1)
def admin_path_prefix() -> str:
    return reverse('admin:index')


def is_admin_request(request) -> bool:
    return request.path.startswith(admin_path_prefix()) and request.user.is_authenticated


class DatabaseSelectionMiddleware:
    '''Picks the database connection a request runs on, so that the admin gets a longer statement timeout than the public API. Anonymous requests never get it, not even to admin paths, so that unauthenticated traffic can't hold a connection for two minutes.'''

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Resolving request.user queries the database, and that lookup belongs on the short connection like any other anonymous work.
        token = current_database_var.set(DEFAULT_DB_ALIAS)
        try:
            if is_admin_request(request):
                current_database_var.set(ADMIN_DATABASE)
            return self.get_response(request)
        finally:
            current_database_var.reset(token)


class DatabaseRouter:
    def db_for_read(self, model, **hints):
        return current_database()

    def db_for_write(self, model, **hints):
        return current_database()

    def allow_relation(self, obj1, obj2, **hints):
        # Every alias points at the same database, so objects fetched through different ones are still related.
        return True

    def allow_migrate(self, db, app_label, **hints):
        return db == DEFAULT_DB_ALIAS
