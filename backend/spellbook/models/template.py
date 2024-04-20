from urllib.parse import urlencode
from django.db import models
from django.utils.html import format_html
from .validators import SCRYFALL_QUERY_HELP, SCRYFALL_QUERY_VALIDATOR, NAME_VALIDATORS
from .scryfall import SCRYFALL_API_CARD_SEARCH, SCRYFALL_WEBSITE_CARD_SEARCH, SCRYFALL_LEGAL_IN_COMMANDER, SCRYFALL_MAX_QUERY_LENGTH


class Template(models.Model):
    MAX_TEMPLATE_NAME_LENGTH = 255
    name = models.CharField(max_length=MAX_TEMPLATE_NAME_LENGTH, blank=False, verbose_name='template name', help_text='short description of the template in natural language', validators=NAME_VALIDATORS)
    scryfall_query = models.CharField(max_length=SCRYFALL_MAX_QUERY_LENGTH, blank=False, verbose_name='Scryfall query', help_text=SCRYFALL_QUERY_HELP, validators=[SCRYFALL_QUERY_VALIDATOR])
    description = models.TextField(blank=True, help_text='Long description of the template', verbose_name='description of the template')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

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
        return urlencode({'q': ' '.join(term for term in [self.scryfall_query, SCRYFALL_LEGAL_IN_COMMANDER] if term != '')})

    def scryfall_api(self):
        return f'{SCRYFALL_API_CARD_SEARCH}?{self.query_string()}'

    def scryfall_link(self):
        if self.scryfall_query == '':
            return 'Empty query'
        link = f'{SCRYFALL_WEBSITE_CARD_SEARCH}?{self.query_string()}'
        return format_html('<a href="{}" target="_blank">{}</a>', link, link)
