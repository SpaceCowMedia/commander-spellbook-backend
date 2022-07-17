from django.db import models
from sortedm2m.fields import SortedManyToManyField


class Feature(models.Model):
    name = models.CharField(max_length=255, unique=True, blank=False, help_text='Short name for a produced effect', verbose_name='name of feature')
    description = models.TextField(blank=True, help_text='Long description of a produced effect', verbose_name='description of feature')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ['name']
        verbose_name = 'feature'
        verbose_name_plural = 'features'

    def __str__(self):
        return self.name


class Card(models.Model):
    name = models.CharField(max_length=255, unique=True, blank=False, help_text='Card name', verbose_name='name of card')
    oracle_id = models.UUIDField(unique=True, blank=True, help_text='Scryfall Oracle ID', verbose_name='Scryfall Oracle ID of card')
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


class Combo(models.Model):
    produces = models.ManyToManyField(
        to=Feature,
        related_name='produced_by_combos',
        help_text='Features that this combo produces',
        verbose_name='produced features')
    needs = models.ManyToManyField(
        to=Feature,
        related_name='needed_by_combos',
        help_text='Features that this combo needs',
        blank=True,
        verbose_name='needed features')
    includes = models.ManyToManyField(
        to=Card,
        related_name='included_in_combos',
        help_text='Cards that this combo includes',
        blank=True,
        verbose_name='included cards')
    prerequisites = models.TextField(blank=True, help_text='Setup instructions for this combo')
    description = models.TextField(blank=True, help_text='Long description of the combo, in steps')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ['created']
        verbose_name = 'combo'
        verbose_name_plural = 'combos'

    def __str__(self):
        if self.pk is None:
            return 'New, unsaved combo'
        return ' + '.join([str(card) for card in self.includes.all()] + [str(feature) for feature in self.needs.all()]) \
            + ' ➡ ' + ' + '.join([str(feature) for feature in self.produces.all()])


class Variant(models.Model):
    class Status(models.TextChoices):
        NOT_WORKING = 'NW'
        DRAFT = 'D'
        OK = 'OK'
        RESTORE = 'R'

    includes = SortedManyToManyField(
        to=Card,
        related_name='included_in_variants',
        help_text='Cards that this variant includes',
        editable=False)
    produces = SortedManyToManyField(
        to=Feature,
        related_name='produced_by_variants',
        help_text='Features that this variant produces',
        editable=False)
    of = models.ManyToManyField(
        to=Combo,
        related_name='variants',
        help_text='Combo that this variant is an instance of',
        editable=False)
    status = models.CharField(choices=Status.choices, default=Status.DRAFT, help_text='Variant status for editors', max_length=2)
    prerequisites = models.TextField(blank=True, help_text='Setup instructions for this variant')
    description = models.TextField(blank=True, help_text='Long description of the variant, in steps')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    unique_id = models.CharField(max_length=128, unique=True, blank=False, help_text='Unique ID for this variant', editable=False)

    class Meta:
        ordering = ['-status', '-created']
        verbose_name = 'variant'
        verbose_name_plural = 'variants'
        indexes = [
            models.Index(fields=['unique_id'], name='unique_variant_index')
        ]

    def __str__(self):
        if self.pk is None:
            return f'New variant with unique id <{self.unique_id}>'
        produces = self.produces.all()[:4]
        return ' + '.join([str(card) for card in self.includes.all()]) \
            + ' ➡ ' + ' + '.join([str(feature) for feature in produces[:3]]) \
            + ('...' if len(produces) > 3 else '')
