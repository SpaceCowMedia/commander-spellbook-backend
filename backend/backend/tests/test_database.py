import warnings
from django.contrib.auth.models import AnonymousUser, User
from django.db import DEFAULT_DB_ALIAS
from django.test import RequestFactory, SimpleTestCase, override_settings
from backend.database import ADMIN_DATABASE, DatabaseRouter, DatabaseSelectionMiddleware, admin_path_prefix, current_database, current_database_var, is_admin_request

SQLITE = {'ENGINE': 'django.db.backends.sqlite3'}
ADMIN_DATABASE_SETTINGS = {DEFAULT_DB_ALIAS: SQLITE, ADMIN_DATABASE: SQLITE}


def request_for(path, user=None):
    request = RequestFactory().get(path)
    request.user = user if user is not None else User()
    return request


class DatabaseTestCase(SimpleTestCase):
    '''These tests only ever ask which database would be used, never query one, so the connections left unopened by the override are not a problem.'''

    def setUp(self):
        super().setUp()
        self.enterContext(warnings.catch_warnings())
        warnings.filterwarnings('ignore', 'Overriding setting DATABASES')
        self.enterContext(override_settings(DATABASES=ADMIN_DATABASE_SETTINGS))


class DatabaseSelectionTests(DatabaseTestCase):
    def test_the_admin_prefix_follows_the_url_configuration(self):
        self.assertEqual(admin_path_prefix(), '/admin/')

    def test_admin_paths_select_the_admin_database(self):
        self.assertTrue(is_admin_request(request_for('/admin/')))
        self.assertTrue(is_admin_request(request_for('/admin/spellbook/combo/1/change/')))

    def test_other_paths_select_the_default_database(self):
        for path in ('/', '/variants/', '/find-my-combos/', '/token/', '/schema/swagger/', '/administrative/'):
            with self.subTest(path=path):
                self.assertFalse(is_admin_request(request_for(path)))

    def test_anonymous_admin_requests_select_the_default_database(self):
        for path in ('/admin/', '/admin/login/', '/admin/spellbook/combo/'):
            with self.subTest(path=path):
                self.assertFalse(is_admin_request(request_for(path, AnonymousUser())), 'Unauthenticated traffic must not reach the longer statement timeout.')

    def test_code_running_outside_a_request_uses_the_default_database(self):
        self.assertEqual(current_database(), DEFAULT_DB_ALIAS, 'Migrations run their data changes through the ORM and must stay on the connection applying the schema changes.')

    def test_the_admin_database_falls_back_to_the_default_one_when_it_is_not_configured(self):
        with override_settings(DATABASES={DEFAULT_DB_ALIAS: SQLITE}):
            token = current_database_var.set(ADMIN_DATABASE)
            try:
                self.assertEqual(current_database(), DEFAULT_DB_ALIAS)
            finally:
                current_database_var.reset(token)


class DatabaseSelectionMiddlewareTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.seen = []
        self.middleware = DatabaseSelectionMiddleware(lambda request: self.seen.append(current_database()))

    def request(self, path, user=None):
        self.middleware(request_for(path, user))
        return self.seen[-1]

    def test_an_admin_request_runs_on_the_admin_database(self):
        self.assertEqual(self.request('/admin/spellbook/combo/'), ADMIN_DATABASE)

    def test_an_api_request_runs_on_the_default_database(self):
        self.assertEqual(self.request('/variants/'), DEFAULT_DB_ALIAS)

    def test_an_anonymous_admin_request_runs_on_the_default_database(self):
        self.assertEqual(self.request('/admin/spellbook/combo/', AnonymousUser()), DEFAULT_DB_ALIAS)

    def test_the_selection_does_not_leak_into_the_next_request_on_the_same_thread(self):
        self.assertEqual(self.request('/admin/'), ADMIN_DATABASE)
        self.assertEqual(current_database(), DEFAULT_DB_ALIAS, 'The admin database is only in use for the duration of the request.')
        self.assertEqual(self.request('/variants/'), DEFAULT_DB_ALIAS)


class DatabaseRouterTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.router = DatabaseRouter()

    def test_queries_go_to_the_currently_selected_database(self):
        for database in (DEFAULT_DB_ALIAS, ADMIN_DATABASE):
            with self.subTest(database=database):
                token = current_database_var.set(database)
                try:
                    self.assertEqual(self.router.db_for_read(User), database)
                    self.assertEqual(self.router.db_for_write(User), database)
                finally:
                    current_database_var.reset(token)

    def test_objects_from_different_databases_are_related(self):
        self.assertIs(self.router.allow_relation(User(), User()), True)

    def test_migrations_only_run_on_the_default_database(self):
        self.assertIs(self.router.allow_migrate(DEFAULT_DB_ALIAS, 'spellbook'), True)
        self.assertIs(self.router.allow_migrate(ADMIN_DATABASE, 'spellbook'), False)

    def test_the_data_changes_of_a_migration_stay_on_the_connection_applying_it(self):
        '''Routing them elsewhere would run them on a second connection, outside the transaction holding the schema changes.'''
        self.assertEqual(self.router.db_for_write(User), DEFAULT_DB_ALIAS)
