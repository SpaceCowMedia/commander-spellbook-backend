from django.conf import settings
from django.test.runner import DiscoverRunner, ParallelTestSuite
from django.test.utils import override_settings


def disable_database_routing():
    '''TestCase only wraps the aliases in cls.databases in a transaction, and a second alias is a separate connection even when it points at the same test database, so routed queries would not see any test data.'''
    if not settings.DATABASE_ROUTERS:
        return None
    override = override_settings(DATABASE_ROUTERS=[])
    override.enable()
    return override


class SpellbookParallelTestSuite(ParallelTestSuite):
    # Spawned workers rebuild their settings from scratch, so they have to disable routing again.
    process_setup = disable_database_routing


class TestRunner(DiscoverRunner):
    parallel_test_suite = SpellbookParallelTestSuite

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self.database_routing_override = disable_database_routing()

    def teardown_test_environment(self, **kwargs):
        if self.database_routing_override is not None:
            self.database_routing_override.disable()
        super().teardown_test_environment(**kwargs)
