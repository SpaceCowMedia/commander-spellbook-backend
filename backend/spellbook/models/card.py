from urllib.parse import urlencode
from django.db import models
from .playable import Playable
from .utils import strip_accents
from .mixins import ScryfallLinkMixin, PreSaveModel
from .feature import Feature


class Card(Playable, PreSaveModel, ScryfallLinkMixin):
    MAX_CARD_NAME_LENGTH = 255
    oracle_id = models.UUIDField(unique=True, blank=True, null=True, help_text='Scryfall Oracle ID', verbose_name='Scryfall Oracle ID of card')
    name = models.CharField(max_length=MAX_CARD_NAME_LENGTH, unique=True, blank=False, help_text='Card name', verbose_name='name of card')
    name_unaccented = models.CharField(max_length=MAX_CARD_NAME_LENGTH, unique=True, blank=False, help_text='Card name without accents', verbose_name='name of card without accents', editable=False)
    type_line = models.CharField(max_length=MAX_CARD_NAME_LENGTH, blank=True, default='', help_text='Card type line', verbose_name='type line of card')
    oracle_text = models.TextField(blank=True, default='', help_text='Card oracle text', verbose_name='oracle text of card')
    features = models.ManyToManyField(
        to=Feature,
        related_name='cards',
        help_text='Features provided by this single card effects or characteristics',
        blank=True)
    added = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ['name']
        verbose_name = 'card'
        verbose_name_plural = 'cards'

    def __str__(self):
        return self.name

    def query_string(self):
        return urlencode({'q': f'!"{self.name}"'})

    def pre_save(self):
        self.name_unaccented = strip_accents(self.name)
