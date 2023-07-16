from typing import Iterable, List, Sequence
from urllib.parse import urlencode
from django.utils.html import format_html
from django.db.models import Model, Manager
from .scryfall import SCRYFALL_WEBSITE_CARD_SEARCH


class ScryfallLinkMixin:
    def query_string(self):
        cards_query = ' or '.join(f'!"{card.name}"' for card in self.cards())
        return urlencode({'q': cards_query})

    def scryfall_link(self):
        link = f'{SCRYFALL_WEBSITE_CARD_SEARCH}?{self.query_string()}'
        return format_html(f'<a href="{link}" target="_blank">Show cards on scryfall</a>')


class PreSaveManager(Manager):
    def bulk_create(self, objs: Iterable['PreSaveModel'], *args, **kwargs) -> List:
        for obj in objs:
            obj.pre_save()
        return super().bulk_create(objs, *args, **kwargs)

    def bulk_update(self, objs: Iterable['PreSaveModel'], fields: Sequence[str], *args, **kwargs) -> int:
        for obj in objs:
            obj.pre_save()
        return super().bulk_update(objs, fields, *args, **kwargs)


class PreSaveModel(Model):
    objects = PreSaveManager()

    def pre_save(self) -> None:
        pass

    def save(self, *args, **kwargs) -> None:
        self.pre_save()
        return super().save(*args, **kwargs)

    class Meta:
        abstract = True
