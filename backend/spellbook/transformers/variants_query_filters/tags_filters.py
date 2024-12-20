from .base import QueryValue, QueryFilter, Q, ValidationError, VariantFilterCollection
from website.models import WebsiteProperty, FEATURED_SET_CODES
from spellbook.models import Variant


def tag_filter(tag_value: QueryValue) -> VariantFilterCollection:
    if tag_value.operator != ':':
        raise ValidationError(f'Operator {tag_value.operator} is not supported for tag search.')
    match tag_value.value.lower():
        case 'preview' | 'previewed' | 'spoiler' | 'spoiled':
            return VariantFilterCollection(
                variants_filters=(
                    QueryFilter(
                        q=Q(spoiler=True),
                        negated=tag_value.is_negated(),
                    ),
                ),
            )
        case 'commander':
            return VariantFilterCollection(
                cards_filters=(
                    QueryFilter(
                        q=Q(must_be_commander=True),
                        negated=tag_value.is_negated(),
                    ),
                ),
            )
        case 'reserved':
            return VariantFilterCollection(
                cards_filters=(
                    QueryFilter(
                        q=Q(card__reserved=True),
                        negated=tag_value.is_negated(),
                    ),
                ),
            )
        case 'mandatory':
            return VariantFilterCollection(
                results_filters=(
                    QueryFilter(
                        q=Q(feature__name='Mandatory Loop'),
                        negated=tag_value.is_negated(),
                    ),
                ),
            )
        case 'lock':
            return VariantFilterCollection(
                results_filters=(
                    QueryFilter(
                        q=Q(feature__name='Lock'),
                        negated=tag_value.is_negated(),
                    ),
                ),
            )
        case 'infinite':
            return VariantFilterCollection(
                results_filters=(
                    QueryFilter(
                        q=Q(feature__name='Infinite'),
                        negated=tag_value.is_negated(),
                    ),
                ),
            )
        case 'risky' | 'allin':
            return VariantFilterCollection(
                results_filters=(
                    QueryFilter(
                        q=Q(feature__name='Risky'),
                        negated=tag_value.is_negated(),
                    ),
                ),
            )
        case 'winning' | 'gamewinning' | 'win':
            return VariantFilterCollection(
                results_filters=(
                    QueryFilter(
                        q=Q(feature__name__in=[
                            'Win the game',
                            'Win the game at the beginning of your next upkeep',
                            'Each opponent loses the game',
                        ]),
                        negated=tag_value.is_negated(),
                    ),
                ),
            )
        case 'featured':
            featured_sets = {s.strip().lower() for s in WebsiteProperty.objects.get(key=FEATURED_SET_CODES).value.split(',')}
            return VariantFilterCollection(
                cards_filters=(
                    QueryFilter(
                        q=Q(card__latest_printing_set__in=featured_sets, card__reprinted=False),
                        negated=tag_value.is_negated(),
                    ),
                ),
            )
        case 'example':
            return VariantFilterCollection(
                variants_filters=(
                    QueryFilter(
                        q=Q(status=Variant.Status.EXAMPLE),
                        negated=tag_value.is_negated(),
                    ),
                ),
            )
        case _:
            raise ValidationError(f'Value "{tag_value.value}" is not supported for tag search.')
