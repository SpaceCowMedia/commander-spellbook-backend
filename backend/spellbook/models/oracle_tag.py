import re
from django.db import models
from django.db.models import Exists, OuterRef, Q
from .card import Card

NOT_ALPHANUMERIC = re.compile(r'[^a-z0-9]')


def oracle_tag_key(name: str) -> str:
    '''The form a tag is looked up by, so that man-land, man land and manland all reach the same tag.

    Scryfall reads a name this way too: otag:extracombat and otag:extra-combat-phase are one query there,
    and the tag is published with extra combat among its aliases.'''
    return NOT_ALPHANUMERIC.sub('', name.lower())


class OracleTag(models.Model):
    '''A tag the Scryfall taggers put on an oracle card, which the otag: search term names.'''
    id = models.UUIDField(primary_key=True, verbose_name='Scryfall ID of tag')
    slug = models.CharField(max_length=255, unique=True, verbose_name='slug of tag')
    label = models.CharField(max_length=255, blank=True, verbose_name='label of tag')
    description = models.TextField(blank=True, verbose_name='description of tag')
    cards: 'models.ManyToManyField[Card, CardOracleTag]' = models.ManyToManyField(
        to=Card,
        through='CardOracleTag',
        related_name='oracle_tags',
        verbose_name='cards carrying the tag',
    )

    class Meta:
        verbose_name = 'oracle tag'
        verbose_name_plural = 'oracle tags'
        ordering = ['slug']

    def __str__(self):
        return self.slug


class OracleTagName(models.Model):
    '''Every name a query can call a tag by: its slug and its aliases, each beside the key it reduces to.'''
    tag = models.ForeignKey(to=OracleTag, on_delete=models.CASCADE, related_name='names')
    name = models.CharField(max_length=255, verbose_name='name of tag')
    normalized_name = models.CharField(max_length=255, unique=True, verbose_name='normalized name of tag')

    class Meta:
        verbose_name = 'oracle tag name'
        verbose_name_plural = 'oracle tag names'
        ordering = ['name']

    def __str__(self):
        return self.name


class CardOracleTag(models.Model):
    '''A card joined to a tag it carries, or to any tag standing above one it carries.

    The hierarchy is resolved when the tags are synced rather than when a query runs, because a tag can
    have no card of its own: the whole membership of removal comes from the twenty five tags below it.'''
    card = models.ForeignKey(to=Card, on_delete=models.CASCADE)
    card_id: int
    tag = models.ForeignKey(to=OracleTag, on_delete=models.CASCADE)
    tag_id: str

    class Meta:
        verbose_name = 'card oracle tag'
        verbose_name_plural = 'card oracle tags'
        constraints = [models.UniqueConstraint(fields=['card', 'tag'], name='unique_card_oracle_tag')]
        indexes = [models.Index(fields=['tag', 'card'])]

    def __str__(self):
        return f'Card {self.card_id} tagged {self.tag_id}'


def oracle_tag_condition(name: str) -> Q:
    '''The cards carrying the named tag, as a condition on Card.

    The name is reduced to the key the sync stored every spelling under, so that manland reaches
    creatureland and man-land reaches it too, without asking a question of its own first. Each tag asks a
    subquery: two conditions on one relation inside a single filter would be asked of the same joined row,
    and no row carries two tags at once.'''
    return Q(Exists(CardOracleTag.objects.filter(card_id=OuterRef('pk'), tag__names__normalized_name=oracle_tag_key(name))))
