from django.conf import settings


def add_version_to_context(request):
    return {'spellbook_version': settings.VERSION}
