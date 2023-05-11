from .settings import * # noqa: F403

ASYNC_GENERATION = False

INSTALLED_APPS = INSTALLED_APPS or []
INSTALLED_APPS.append('django_extensions')
