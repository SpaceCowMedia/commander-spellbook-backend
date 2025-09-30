from lark import Lark, Transformer, LarkError, UnexpectedToken, UnexpectedCharacters
from django.db.models import Q, QuerySet
from django.core.exceptions import ValidationError
from spellbook.models import TemplateInVariant, TemplateReplacement, Variant, FeatureProducedByVariant, CardInVariant, Card
from .variants_query_filters.template_search_filters import template_search_filter
from .variants_query_filters.varant_variants_filters import variants_filter
from .variants_query_filters.card_search_filters import card_search_filter
from .variants_query_filters.card_type_filters import card_type_filter
from .variants_query_filters.card_oracle_filters import card_oracle_filter
from .variants_query_filters.card_keyword_filters import card_keyword_filter
from .variants_query_filters.card_mana_value_filters import card_mana_value_filter
from .variants_query_filters.variant_identity_filters import identity_filter
from .variants_query_filters.variant_prerequisites_filters import prerequisites_filter
from .variants_query_filters.variant_description_filters import description_filter
from .variants_query_filters.results_filters import results_filter
from .variants_query_filters.variant_id_filters import id_filter
from .variants_query_filters.tags_filters import tag_filter
from .variants_query_filters.commander_search_filters import commander_filter
from .variants_query_filters.variant_legality_filters import legality_filter
from .variants_query_filters.variant_price_filters import price_filter
from .variants_query_filters.variant_popularity_filters import popularity_filter
from .variants_query_filters.bracket_filters import bracket_filter
from .variants_query_filters.base import QueryValue, VariantFilterCollection
from ..parsers.variants_query_grammar import VARIANTS_QUERY_GRAMMAR


class VariantsQueryTransformer(Transformer):
    # region filters
    def card_search_shortcut(self, values):
        q = QueryValue.from_short_string(values[0], key='card', operator=':')
        return card_search_filter(q)

    def card_search(self, values):
        q = QueryValue.from_string(values[0])
        return card_search_filter(q)

    def template_search(self, values):
        q = QueryValue.from_string(values[0])
        return template_search_filter(q)

    def card_type_search(self, values):
        q = QueryValue.from_string(values[0])
        return card_type_filter(q)

    def card_oracle_search(self, values):
        q = QueryValue.from_string(values[0])
        return card_oracle_filter(q)

    def card_keyword_search(self, values):
        q = QueryValue.from_string(values[0])
        return card_keyword_filter(q)

    def card_mana_value_search(self, values):
        q = QueryValue.from_string(values[0])
        return card_mana_value_filter(q)

    def identity_search(self, values):
        q = QueryValue.from_string(values[0])
        return identity_filter(q)

    def prerequisites_search(self, values):
        q = QueryValue.from_string(values[0])
        return prerequisites_filter(q)

    def steps_search(self, values):
        q = QueryValue.from_string(values[0])
        return description_filter(q)

    def results_search(self, values):
        q = QueryValue.from_string(values[0])
        return results_filter(q)

    def spellbook_id_search(self, values):
        q = QueryValue.from_string(values[0])
        return id_filter(q)

    def tag_search(self, values):
        q = QueryValue.from_string(values[0])
        return tag_filter(q)

    def commander_search(self, values):
        q = QueryValue.from_string(values[0])
        return commander_filter(q)

    def legality_search(self, values):
        q = QueryValue.from_string(values[0])
        return legality_filter(q)

    def price_search(self, values):
        q = QueryValue.from_string(values[0])
        return price_filter(q)

    def popularity_search(self, values):
        q = QueryValue.from_string(values[0])
        return popularity_filter(q)

    def variants_search(self, values):
        q = QueryValue.from_string(values[0])
        return variants_filter(q)

    def bracket_search(self, values):
        q = QueryValue.from_string(values[0])
        return bracket_filter(q)
    # endregion

    # region composition
    def matcher(self, values):
        match values[0]:
            case '-':
                return ~values[1]
            case _:
                return values[0]

    def factor(self, values):
        return values[1]

    def term(self, values):
        return values[0] & values[-1]

    def expression(self, values):
        raise NotImplementedError('OR composition is not implemented.')

    def start(self, values):
        if not values:
            return VariantFilterCollection()
        return values[0]
    # endregion


PARSER = Lark(VARIANTS_QUERY_GRAMMAR, parser='lalr', transformer=VariantsQueryTransformer())
MAX_QUERY_LENGTH = 1024
MAX_QUERY_PARAMETERS = 20


def variants_query_parser(base: QuerySet[Variant], query_string: str) -> QuerySet:
    query_string = query_string.strip()
    if len(query_string) > MAX_QUERY_LENGTH:
        raise ValidationError('Search query is too long.')
    try:
        filters: VariantFilterCollection = PARSER.parse(query_string)  # type: ignore
        if len(filters) > MAX_QUERY_PARAMETERS:
            raise ValidationError('Too many search parameters.')
        filtered_variants = base
        for filter in filters.variants_filters:
            filtered_variants = filtered_variants.exclude(filter.q) if filter.exclude else filtered_variants.filter(filter.q)
            base = filtered_variants
        for filter in filters.cardinvariants_filters:
            matching_cardinvariants = CardInVariant.objects.filter(filter.q)
            q = Q(pk__in=matching_cardinvariants.values('variant_id'))
            filtered_variants = filtered_variants.exclude(q) if filter.exclude else filtered_variants.filter(q)
        for filter in filters.templates_filters:
            filtered_templates = TemplateInVariant.objects.filter(filter.q)
            q = Q(pk__in=filtered_templates.values('variant_id'))
            filtered_variants = filtered_variants.exclude(q) if filter.exclude else filtered_variants.filter(q)
        for filter in filters.results_filters:
            filtered_produces = FeatureProducedByVariant.objects.filter(filter.q)
            q = Q(pk__in=filtered_produces.values('variant_id'))
            filtered_variants = filtered_variants.exclude(q) if filter.exclude else filtered_variants.filter(q)
        for filter in filters.cards_filters:
            matching_cards = Card.objects.filter(filter.q)
            if filter.exclude:
                # templates_to_exclude = TemplateReplacement.objects \
                #     .values('template') \
                #     .exclude(card__in=Card.objects.exclude(filter.q))
                filtered_variants = filtered_variants.exclude(
                    Q(
                        pk__in=CardInVariant.objects
                        .values('variant_id')
                        .filter(card__in=matching_cards),
                    ) | Q(
                        # pk__in=TemplateInVariant.objects
                        # .values('variant_id')
                        # .filter(template__in=templates_to_exclude),
                    ),
                )
            else:
                filtered_variants = filtered_variants.filter(
                    Q(
                        pk__in=CardInVariant.objects
                        .values('variant_id')
                        .filter(card__in=matching_cards),
                    ) | Q(
                        # pk__in=TemplateInVariant.objects
                        # .values('variant_id')
                        # .filter(template__replacements__in=matching_cards),
                    ),
                )
        return filtered_variants
    except UnexpectedToken as e:
        if e.token.type == '$END':
            raise ValidationError(f'Invalid search query: something is missing after character {e.column}.')
        raise ValidationError(f'Invalid search query: something is wrong at character {e.column + 1}.')
    except UnexpectedCharacters as e:
        raise ValidationError(f'Invalid search query: unexpected character {query_string[e.column - 1]} at position {e.column}.')
    except LarkError as e:
        raise ValidationError(f'Invalid search query: {e}')
