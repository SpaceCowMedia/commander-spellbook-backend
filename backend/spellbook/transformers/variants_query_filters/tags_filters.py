from .base import QueryValue, Q, ValidationError, VariantQuery
from website.models import WebsiteProperty, FEATURED_SET_CODES_PROPERTIES, FEATURED_TABS_COUNT
from spellbook.models import Card, CardInVariant, Feature, FeatureProducedByVariant, Variant


FEATURED_TABS_TAGS = [f'featured-{i}' for i in range(1, FEATURED_TABS_COUNT + 1)]


def tag_filter(qv: QueryValue) -> VariantQuery:
    if qv.operator != ':':
        raise ValidationError(f'Operator {qv.operator} is not supported for tag search.')
    match qv.value.lower():
        case 'preview' | 'previewed' | 'spoiler' | 'spoiled':
            return qv.to_filter(Q(spoiler=True))
        case 'commander':
            return qv.to_filter(Q(must_be_commander=True), CardInVariant)
        case 'reserved':
            return qv.to_filter(Q(reserved=True), Card)
        case 'mandatory':
            return qv.to_filter(Q(feature__name='Mandatory Loop'), FeatureProducedByVariant)
        case 'lock':
            return qv.to_filter(Q(feature__name='Lock'), FeatureProducedByVariant)
        case 'mld' | 'masslanddestruction' | 'masslanddenial' | 'masslandremoval':
            return qv.to_filter(Q(feature__name__in=[
                'Mass Land Destruction',
                'Mass Land Denial',
                'Mass Land Removal',
            ]), FeatureProducedByVariant)
        case 'infinite':
            return qv.to_filter(Q(feature__name__istartswith='infinite'), FeatureProducedByVariant)
        case 'risky' | 'allin':
            return qv.to_filter(Q(feature__name='Risky'), FeatureProducedByVariant)
        case 'winning' | 'gamewinning' | 'win':
            return qv.to_filter(Q(feature__name__in=[
                'Win the game',
                'Win the game at the beginning of your next upkeep',
                'Each opponent loses the game',
            ]), FeatureProducedByVariant)
        case s if s == 'featured' or s in FEATURED_TABS_TAGS:
            if s == 'featured':
                keys = FEATURED_SET_CODES_PROPERTIES
            else:
                keys = [FEATURED_SET_CODES_PROPERTIES[FEATURED_TABS_TAGS.index(s)]]
            featured_sets = {
                s.strip().lower()
                for p in WebsiteProperty.objects
                .filter(key__in=keys)
                .values_list('value', flat=True)
                for s in p.split(',')
                if s.strip()
            }
            return qv.to_filter(Q(card__latest_printing_set__in=featured_sets, card__reprinted=False), CardInVariant)
        case 'example':
            return qv.to_filter(Q(status=Variant.Status.EXAMPLE))
        case 'hulkline' | 'meatandeggs' | 'hulktutorable':
            return qv.to_filter(Q(hulkline=True))
        case 'complete':
            return qv.to_filter(Q(feature__status=Feature.Status.STANDALONE), FeatureProducedByVariant)
        case _:
            raise ValidationError(f'Value "{qv.value}" is not supported for tag search.')
