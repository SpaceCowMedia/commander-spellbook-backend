from urllib.parse import urlencode
from django.utils import timezone
from django.db import OperationalError, models, transaction
from sortedm2m.fields import SortedManyToManyField
from django.contrib.auth.models import User
from .validators import MANA_VALIDATOR, TEXT_VALIDATORS, IDENTITY_VALIDATOR, SCRYFALL_QUERY_VALIDATOR, SCRYFALL_QUERY_HELP
from django.utils.html import format_html
from .scryfall import SCRYFALL_API_CARD_SEARCH, SCRYFALL_WEBSITE_CARD_SEARCH, SCRYFALL_LEGAL_IN_COMMANDER


class Feature(models.Model):
    name = models.CharField(max_length=255, unique=True, blank=False, help_text='Short name for a produced effect', verbose_name='name of feature')
    description = models.TextField(blank=True, help_text='Long description of a produced effect', verbose_name='description of feature')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    utility = models.BooleanField(default=False, help_text='Is this a utility feature? Utility features are hidden to the end users', verbose_name='is utility')

    class Meta:
        ordering = ['name']
        verbose_name = 'feature'
        verbose_name_plural = 'features'

    def __str__(self):
        return self.name


class Card(models.Model):
    name = models.CharField(max_length=255, unique=True, blank=False, help_text='Card name', verbose_name='name of card')
    oracle_id = models.UUIDField(unique=True, blank=True, null=True, help_text='Scryfall Oracle ID', verbose_name='Scryfall Oracle ID of card')
    features = models.ManyToManyField(
        to=Feature,
        related_name='cards',
        help_text='Features provided by this single card effects or characteristics',
        blank=True)
    identity = models.CharField(max_length=5, blank=True, help_text='Card mana identity', verbose_name='mana identity of card', validators=[IDENTITY_VALIDATOR])
    legal = models.BooleanField(default=True, help_text='Is this card legal in Commander?', verbose_name='is legal')
    added = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ['name']
        verbose_name = 'card'
        verbose_name_plural = 'cards'

    def __str__(self):
        return self.name


class Template(models.Model):
    name = models.CharField(max_length=255, blank=False, verbose_name='template name', help_text='short description of the template in natural language')
    scryfall_query = models.CharField(max_length=255, blank=False, verbose_name='Scryfall query', help_text=SCRYFALL_QUERY_HELP, validators=[SCRYFALL_QUERY_VALIDATOR])
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ['name']
        verbose_name = 'card template'
        verbose_name_plural = 'templates'
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
        return format_html(f'<a href="{link}" target="_blank">{link}</a>')


class UsesCardsMixin:
    def query_string(self):
        cards_query = ' or '.join(f'!"{card.name}"' for card in self.cards())
        return urlencode({'q': cards_query})

    def scryfall_link(self):
        link = f'{SCRYFALL_WEBSITE_CARD_SEARCH}?{self.query_string()}'
        return format_html(f'<a href="{link}" target="_blank">Show cards on scryfall</a>')


class Combo(models.Model, UsesCardsMixin):
    uses = models.ManyToManyField(
        to=Card,
        related_name='used_in_combos',
        help_text='Cards that this combo uses',
        blank=True,
        verbose_name='used cards',
        through='CardInCombo')
    needs = models.ManyToManyField(
        to=Feature,
        related_name='needed_by_combos',
        help_text='Features that this combo needs',
        blank=True,
        verbose_name='needed features')
    requires = models.ManyToManyField(
        to=Template,
        related_name='required_by_combos',
        help_text='Templates that this combo requires',
        blank=True,
        verbose_name='required templates',
        through='TemplateInCombo')
    produces = models.ManyToManyField(
        to=Feature,
        related_name='produced_by_combos',
        help_text='Features that this combo produces',
        verbose_name='produced features')
    removes = models.ManyToManyField(
        to=Feature,
        related_name='removed_by_combos',
        help_text='Features that this combo removes',
        blank=True,
        verbose_name='removed features')
    mana_needed = models.CharField(blank=True, max_length=200, default='', help_text='Mana needed for this combo. Use the {1}{W}{U}{B}{R}{G}{B/P}... format.', validators=[MANA_VALIDATOR])
    other_prerequisites = models.TextField(blank=True, default='', help_text='Other prerequisites for this combo.', validators=TEXT_VALIDATORS)
    description = models.TextField(blank=True, help_text='Long description of the combo, in steps', validators=TEXT_VALIDATORS)
    generator = models.BooleanField(default=True, help_text='Is this combo a generator for variants?', verbose_name='is generator')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    def cards(self):
        return self.uses.order_by('cardincombo')

    def templates(self):
        return self.requires.order_by('templateincombo')

    class Meta:
        ordering = ['created']
        verbose_name = 'combo'
        verbose_name_plural = 'combos'

    def __str__(self):
        if self.pk is None:
            return 'New, unsaved combo'
        return self.ingredients() \
            + ' ➡ ' + ' + '.join([str(feature) for feature in self.produces.all()]) \
            + (' - ' + ' - '.join([str(feature) for feature in self.removes.all()]) if self.removes.exists() else '')

    def ingredients(self):
        return ' + '.join([str(card) for card in self.cards()] + [str(feature) for feature in self.needs.all()] + [str(template) for template in self.templates()])

    def variants_for_editors(self):
        return self.variants.order_by(models.Case(
            models.When(status=Variant.Status.DRAFT, then=0),
            models.When(status=Variant.Status.NEW, then=1),
            default=2
        ), '-updated')


class Job(models.Model):
    class Status(models.TextChoices):
        SUCCESS = 'S'
        FAILURE = 'F'
        PENDING = 'P'
    name = models.CharField(max_length=255, blank=False, verbose_name='name of job')
    created = models.DateTimeField(auto_now_add=True, blank=False)
    expected_termination = models.DateTimeField(blank=False)
    termination = models.DateTimeField(blank=True, null=True)
    status = models.CharField(choices=Status.choices, default=Status.PENDING, max_length=2, blank=False)
    message = models.TextField(blank=True)
    started_by = models.ForeignKey(
        to=User,
        related_name='started_jobs',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        help_text='User that started this job')

    def start(name: str, duration: timezone.timedelta, user: User):
        try:
            with transaction.atomic():
                if Job.objects.filter(
                        name=name,
                        expected_termination__gte=timezone.now(),
                        status=Job.Status.PENDING).exists():
                    return None
                return Job.objects.create(
                    name=name,
                    expected_termination=timezone.now() + duration,
                    started_by=user)
        except OperationalError:
            return None

    class Meta:
        ordering = ['-created', 'name']
        verbose_name = 'job'
        verbose_name_plural = 'jobs'
        indexes = [
            models.Index(fields=['name'], name='job_name_index')
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(expected_termination__gte=models.F('created')), name='job_expected_termination_gte_created')
        ]

    def __str__(self):
        return self.name


class Variant(models.Model, UsesCardsMixin):
    class Status(models.TextChoices):
        NEW = 'N'
        DRAFT = 'D'
        NOT_WORKING = 'NW'
        OK = 'OK'
        RESTORE = 'R'

    uses = models.ManyToManyField(
        to=Card,
        related_name='used_in_variants',
        help_text='Cards that this variant uses',
        editable=False,
        through='CardInVariant')
    requires = models.ManyToManyField(
        to=Template,
        related_name='required_by_variants',
        help_text='Templates that this variant requires',
        blank=True,
        verbose_name='required templates',
        through='TemplateInVariant')
    produces = SortedManyToManyField(
        to=Feature,
        related_name='produced_by_variants',
        help_text='Features that this variant produces',
        editable=False)
    includes = models.ManyToManyField(
        to=Combo,
        related_name='included_in_variants',
        help_text='Combo that this variant includes',
        editable=False)
    of = models.ManyToManyField(
        to=Combo,
        related_name='variants',
        help_text='Combo that this variant is an instance of',
        editable=False)
    status = models.CharField(choices=Status.choices, default=Status.NEW, help_text='Variant status for editors', max_length=2)
    mana_needed = models.CharField(blank=True, max_length=200, default='', help_text='Mana needed for this combo. Use the {1}{W}{U}{B}{R}{G}{B/P}... format.', validators=[MANA_VALIDATOR])
    other_prerequisites = models.TextField(blank=True, default='', help_text='Other prerequisites for this variant.', validators=TEXT_VALIDATORS)
    description = models.TextField(blank=True, help_text='Long description, in steps', validators=TEXT_VALIDATORS)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    unique_id = models.CharField(max_length=128, unique=True, blank=False, help_text='Unique ID for this variant', editable=False)
    frozen = models.BooleanField(default=False, blank=False, help_text='Is this variant undeletable?', verbose_name='is frozen')
    legal = models.BooleanField(default=True, blank=False, help_text='Is this variant legal in Commander?', verbose_name='is legal')
    identity = models.CharField(max_length=5, blank=True, help_text='Mana identity', verbose_name='mana identity', editable=False, validators=[IDENTITY_VALIDATOR])
    generated_by = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, editable=False, help_text='Job that generated this variant', related_name='variants')

    class Meta:
        ordering = ['-status', '-created']
        verbose_name = 'variant'
        verbose_name_plural = 'variants'
        indexes = [
            models.Index(fields=['unique_id'], name='unique_variant_index')
        ]

    def cards(self):
        return self.uses.order_by('cardinvariant')

    def templates(self):
        return self.requires.order_by('templateinvariant')

    def __str__(self):
        if self.pk is None:
            return f'New variant with unique id <{self.unique_id}>'
        produces = self.produces.all()[:4]
        return ' + '.join([str(card) for card in self.cards()] + [str(template) for template in self.templates()]) \
            + ' ➡ ' + ' + '.join([str(feature) for feature in produces[:3]]) \
            + ('...' if len(produces) > 3 else '')


# Through models
class IngredientInCombination(models.Model):
    class ZoneLocation(models.TextChoices):
        HAND = 'H'
        BATTLEFIELD = 'B'
        COMMAND_ZONE = 'C'
        GRAVEYARD = 'G'
        LIBRARY = 'L'
        EXILE = 'E'
        ANY = 'A'
    order = models.IntegerField(blank=False, help_text='Order of the card in the combo.', verbose_name='order')
    zone_location = models.CharField(choices=ZoneLocation.choices, default=ZoneLocation.HAND, max_length=2, blank=False, help_text='Starting location for the card.', verbose_name='starting location')
    card_state = models.CharField(max_length=200, blank=True, default='', help_text='State of the card in its starting location.', validators=TEXT_VALIDATORS, verbose_name='starting card state')

    class Meta:
        abstract = True
        ordering = ['order', 'id']


class CardInCombo(IngredientInCombination):
    card = models.ForeignKey(to=Card, on_delete=models.CASCADE)
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)

    class Meta(IngredientInCombination.Meta):
        unique_together = [('card', 'combo')]


class CardInVariant(IngredientInCombination):
    card = models.ForeignKey(to=Card, on_delete=models.CASCADE)
    variant = models.ForeignKey(to=Variant, on_delete=models.CASCADE)

    class Meta(IngredientInCombination.Meta):
        unique_together = [('card', 'variant')]


class TemplateInCombo(IngredientInCombination):
    template = models.ForeignKey(to=Template, on_delete=models.CASCADE)
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)

    class Meta(IngredientInCombination.Meta):
        unique_together = [('template', 'combo')]


class TemplateInVariant(IngredientInCombination):
    template = models.ForeignKey(to=Template, on_delete=models.CASCADE)
    variant = models.ForeignKey(to=Variant, on_delete=models.CASCADE)

    class Meta(IngredientInCombination.Meta):
        unique_together = [('template', 'variant')]
