from urllib.parse import urlencode
from django.db import models
from django.utils.html import format_html
from spellbook.models import Card
from .validators import SCRYFALL_QUERY_HELP, SCRYFALL_QUERY_VALIDATOR, NAME_VALIDATORS
from .scryfall import SCRYFALL_API_CARD_SEARCH, SCRYFALL_WEBSITE_CARD_SEARCH, SCRYFALL_LEGAL_IN_COMMANDER, SCRYFALL_MAX_QUERY_LENGTH


class Template(models.Model):
    MAX_TEMPLATE_NAME_LENGTH = 255
    id: int
    name = models.CharField(blank=False, max_length=MAX_TEMPLATE_NAME_LENGTH, unique=True, verbose_name='template name', help_text='short description of the template in natural language', validators=NAME_VALIDATORS)
    scryfall_query = models.CharField(blank=True, null=True, max_length=SCRYFALL_MAX_QUERY_LENGTH, verbose_name='Scryfall query', help_text=SCRYFALL_QUERY_HELP, validators=[SCRYFALL_QUERY_VALIDATOR])
    description = models.TextField(blank=True, help_text='Long description of the template', verbose_name='description of the template')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    replacements = models.ManyToManyField(
        to=Card,
        through='TemplateReplacement',
        related_name='replaces',
        help_text='Cards that are valid replacements of this template',
        blank=True,
        verbose_name='replacements for template',
    )

    class Meta:
        verbose_name = 'card template'
        verbose_name_plural = 'templates'
        default_manager_name = 'objects'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name'], name='card_template_name_index')
        ]

    def __str__(self):
        return self.name

    def query_string(self):
        if self.scryfall_query is None:
            return None
        return urlencode({'q': ' '.join(term for term in [self.scryfall_query, SCRYFALL_LEGAL_IN_COMMANDER] if term != '')})

    def scryfall_api(self):
        query = self.query_string()
        if query is None:
            return None
        return f'{SCRYFALL_API_CARD_SEARCH}?{query}'

    def scryfall_link(self, raw=False):
        if self.scryfall_query is None:
            return None
        if self.scryfall_query == '':
            return 'Empty query'
        link = f'{SCRYFALL_WEBSITE_CARD_SEARCH}?{self.query_string()}'
        if raw:
            return link
        return format_html('<a href="{}" target="_blank">{}</a>', link, link)


class TemplateReplacement(models.Model):
    id: int
    card = models.ForeignKey(to=Card, on_delete=models.CASCADE)
    card_id: int
    template = models.ForeignKey(to=Template, on_delete=models.CASCADE)
    template_id: int

    def __str__(self):
        return f'Card {self.card_id} as replacement for template {self.template_id}'

    class Meta:
        unique_together = [('card', 'template')]
