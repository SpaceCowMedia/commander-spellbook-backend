from lark import Lark, Transformer
from django.db.models import QuerySet
from spellbook.models import Variant
from .query_parsing import parse_query
from .variants_query_filters.template_search_filters import template_search_filter
from .variants_query_filters.varant_variants_filters import variants_filter
from .variants_query_filters.card_search_filters import card_search_filter
from .variants_query_filters.card_type_filters import card_type_filter
from .variants_query_filters.card_oracle_filters import card_oracle_filter
from .variants_query_filters.card_keyword_filters import card_keyword_filter
from .variants_query_filters.card_mana_value_filters import card_mana_value_filter
from .variants_query_filters.card_color_filters import card_color_filter
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
from .variants_query_filters.base import QueryValue, VariantQuery
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

    def card_color_search(self, values):
        q = QueryValue.from_string(values[0])
        return card_color_filter(q)

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
    def factor(self, values):
        match values[0]:
            case '-':
                return ~values[1]
            case _:
                return values[1]

    def term(self, values):
        return values[0] & values[-1]

    def expression(self, values):
        return values[0] | values[-1]

    def start(self, values):
        if not values:
            return VariantQuery()
        return values[0]
    # endregion


PARSER = Lark(VARIANTS_QUERY_GRAMMAR, parser='lalr', transformer=VariantsQueryTransformer())


def variants_query_parser(base: QuerySet[Variant], query_string: str) -> QuerySet:
    query: VariantQuery = parse_query(PARSER, query_string)
    return base.filter(query.to_q())
