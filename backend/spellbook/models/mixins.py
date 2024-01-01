from typing import Iterable, List, Sequence
from urllib.parse import urlencode
from django.utils.html import format_html
from django.db.models import Model, Manager
from .scryfall import SCRYFALL_WEBSITE_CARD_SEARCH


class ScryfallLinkMixin:
    def cards(self) -> list:
        raise NotImplementedError

    def query_string(self, cards: list | None = None):
        cards = cards or self.cards()
        cards_query = ' or '.join(f'!"{card.name}"' for card in cards)
        return urlencode({'q': cards_query})

    def scryfall_link(self):
        cards = self.cards()
        link = f'{SCRYFALL_WEBSITE_CARD_SEARCH}?{self.query_string(cards=cards)}'
        plural = 's' if len(cards) > 1 else ''
        return format_html(f'<a href="{link}" target="_blank">Show card{plural} on scryfall</a>')


class PreSaveManager(Manager):
    def bulk_create(self, objs: Iterable['PreSaveModelMixin'], *args, **kwargs) -> List:
        for obj in objs:
            obj.pre_save()
        return super().bulk_create(objs, *args, **kwargs)

    def bulk_update(self, objs: Iterable['PreSaveModelMixin'], fields: Sequence[str], *args, **kwargs) -> int:
        for obj in objs:
            obj.pre_save()
        return super().bulk_update(objs, fields, *args, **kwargs)


class PreSaveModelMixin(Model):
    objects = PreSaveManager()

    def pre_save(self) -> None:
        pass

    def save(self, *args, **kwargs) -> None:
        self.pre_save()
        return super().save(*args, **kwargs)

    class Meta:
        abstract = True
