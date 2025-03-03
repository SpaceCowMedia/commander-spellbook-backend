from .base import QueryValue, Q, ValidationError, VariantFilterCollection
from website.models import WebsiteProperty, FEATURED_SET_CODES
from spellbook.models import Feature, Variant


def tag_filter(qv: QueryValue) -> VariantFilterCollection:
    if qv.operator != ':':
        raise ValidationError(f'Operator {qv.operator} is not supported for tag search.')
    match qv.value.lower():
        case 'preview' | 'previewed' | 'spoiler' | 'spoiled':
            return VariantFilterCollection(variants_filters=(qv.to_query_filter(
                Q(spoiler=True),
            ),))
        case 'commander':
            return VariantFilterCollection(cards_filters=(qv.to_query_filter(
                Q(must_be_commander=True),
            ),))
        case 'reserved':
            return VariantFilterCollection(cards_filters=(qv.to_query_filter(
                Q(card__reserved=True),
            ),))
        case 'mandatory':
            return VariantFilterCollection(results_filters=(qv.to_query_filter(
                Q(feature__name='Mandatory Loop'),
            ),))
        case 'lock':
            return VariantFilterCollection(results_filters=(qv.to_query_filter(
                Q(feature__name='Lock'),
            ),))
        case 'infinite':
            return VariantFilterCollection(results_filters=(qv.to_query_filter(
                Q(feature__name__istartswith='infinite'),
            ),))
        case 'risky' | 'allin':
            return VariantFilterCollection(results_filters=(qv.to_query_filter(
                Q(feature__name='Risky'),
            ),))
        case 'winning' | 'gamewinning' | 'win':
            return VariantFilterCollection(results_filters=(qv.to_query_filter(
                Q(feature__name__in=[
                    'Win the game',
                    'Win the game at the beginning of your next upkeep',
                    'Each opponent loses the game',
                ]),
            ),))
        case 'featured':
            featured_sets = {s.strip().lower() for s in WebsiteProperty.objects.get(key=FEATURED_SET_CODES).value.split(',')}
            return VariantFilterCollection(cards_filters=(qv.to_query_filter(
                Q(card__latest_printing_set__in=featured_sets, card__reprinted=False),
            ),))
        case 'example':
            return VariantFilterCollection(variants_filters=(qv.to_query_filter(
                Q(status=Variant.Status.EXAMPLE),
            ),))
        case 'hulkline' | 'meatandeggs' | 'hulktutorable':
            return VariantFilterCollection(variants_filters=(qv.to_query_filter(
                Q(hulkline=True),
            ),))
        case 'complete':
            return VariantFilterCollection(results_filters=(qv.to_query_filter(
                Q(feature__status=Feature.Status.STANDALONE),
            ),))
        case _:
            raise ValidationError(f'Value "{qv.value}" is not supported for tag search.')
