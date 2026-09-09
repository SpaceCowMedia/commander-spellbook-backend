from urllib.parse import urlencode
from django.db import models
from django.dispatch import receiver
from django.db.models.signals import m2m_changed, post_save
from django.utils.html import format_html
from spellbook.models import Card
from .mixins import NamedModel
from .utils import case_insensitive_trigram_indexes
from .recipe import update_variants, update_combo_names
from .validators import SCRYFALL_QUERY_HELP, SCRYFALL_QUERY_VALIDATORS, NAME_VALIDATORS
from .scryfall import scryfall_query_legal_in_commander, SCRYFALL_API_CARD_SEARCH, SCRYFALL_WEBSITE_CARD_SEARCH, SCRYFALL_MAX_QUERY_LENGTH


class Template(NamedModel):
    MAX_TEMPLATE_NAME_LENGTH = 255
    id: int
    name = NamedModel.name_field(max_length=MAX_TEMPLATE_NAME_LENGTH, verbose_name='template name', help_text='short description of the template in natural language', validators=NAME_VALIDATORS)
    scryfall_query = models.CharField(blank=True, null=True, max_length=SCRYFALL_MAX_QUERY_LENGTH, verbose_name='Scryfall query', help_text=SCRYFALL_QUERY_HELP, validators=SCRYFALL_QUERY_VALIDATORS)
    description = models.TextField(blank=True, help_text='Long description of the template', verbose_name='description of the template')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    replacements: 'models.ManyToManyField[Card, TemplateReplacement]' = models.ManyToManyField(
        to=Card,
        through='TemplateReplacement',
        related_name='replaces',
        help_text='Cards that are valid replacements of this template',
        blank=True,
        verbose_name='replacements for template',
    )
    matches: 'models.ManyToManyField[Card, TemplateMatch]' = models.ManyToManyField(
        to=Card,
        through='TemplateMatch',
        related_name='matched_by',
        editable=False,
        verbose_name='cards matching template',
        help_text='Cards this template stands for, whether its query found them or an editor listed them',
    )

    _scryfall_query: str | None = None

    @property
    def requeried(self) -> bool:
        '''Whether this instance carries a query the database does not hold yet, so that what the
        template stands for has to be worked out again.'''
        return self._scryfall_query != self.scryfall_query

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._scryfall_query = instance.__dict__.get('scryfall_query')
        return instance

    def save(self, *args, **kwargs):
        result = super().save(*args, **kwargs)
        # the receivers of post_save ran against the old query, that is now the stored one
        self._scryfall_query = self.scryfall_query
        return result

    class Meta:
        verbose_name = 'card template'
        verbose_name_plural = 'templates'
        default_manager_name = 'objects'
        ordering = ['name']
        indexes = case_insensitive_trigram_indexes('template', 'name')

    def __str__(self):
        return self.name

    def query_string(self):
        if self.scryfall_query is None:
            return None
        return urlencode({'q': scryfall_query_legal_in_commander(self.scryfall_query)})

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


@receiver(post_save, sender=Template, dispatch_uid='update_variant_fields')
def update_variant_fields(sender, instance: Template, created, raw, **kwargs):
    # the name of a template is the only thing it contributes to its variants, from their name to the fields deduced from it
    if raw or created or not instance.renamed_from:
        return
    update_variants(requires=instance)


@receiver(post_save, sender=Template, dispatch_uid='update_combo_fields')
def update_combo_fields(sender, instance: Template, created, raw, **kwargs):
    if raw or created or not instance.renamed_from:
        return
    update_combo_names(requires=instance)


class TemplateReplacement(models.Model):
    id: int
    card = models.ForeignKey(to=Card, to_field='number', on_delete=models.CASCADE, limit_choices_to={'number__isnull': False})
    card_id: int
    template = models.ForeignKey(to=Template, on_delete=models.CASCADE)
    template_id: int

    def __str__(self):
        return f'Card {self.card_id} as replacement for template {self.template_id}'

    class Meta:
        unique_together = [('card', 'template')]


class TemplateMatch(models.Model):
    '''A card this template stands for.

    Both kinds of template land here, the ones an editor filled a replacement list for and the ones a
    Scryfall query defines, so that everything downstream counts them the same way.'''
    id: int
    card = models.ForeignKey(to=Card, on_delete=models.CASCADE)
    card_id: int
    template = models.ForeignKey(to=Template, on_delete=models.CASCADE)
    template_id: int

    class Meta:
        verbose_name = 'template match'
        verbose_name_plural = 'template matches'
        constraints = [models.UniqueConstraint(fields=['card', 'template'], name='unique_template_match')]
        indexes = [models.Index(fields=['template', 'card'])]

    def __str__(self):
        return f'Card {self.card_id} matching template {self.template_id}'


@receiver(post_save, sender=Template, dispatch_uid='update_template_matches')
def update_matches_on_save(sender, instance: Template, created, raw, **kwargs):
    # what a template stands for is recomputed whole, for the one template being saved, and only when
    # its query is what changed: every other edit leaves the same cards behind it
    if raw or not created and not instance.requeried:
        return
    from spellbook.tasks.template_matches import update_template_matches
    update_template_matches(Template.objects.filter(pk=instance.pk))


@receiver(m2m_changed, sender=TemplateReplacement, dispatch_uid='update_template_matches_on_replacements')
def update_matches_on_replacements(sender, instance, action, reverse, pk_set, **kwargs):
    # editing a replacement list fires no post_save of its own, so the template would keep stale matches
    if action not in ('post_add', 'post_remove', 'post_clear'):
        return
    from spellbook.tasks.template_matches import update_template_matches
    templates = Template.objects.filter(pk__in=pk_set) if reverse else Template.objects.filter(pk=instance.pk)
    update_template_matches(templates)
