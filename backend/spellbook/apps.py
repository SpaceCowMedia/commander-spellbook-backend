from django.apps import AppConfig


class SpellbookConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'spellbook'

    def ready(self):
        pass
