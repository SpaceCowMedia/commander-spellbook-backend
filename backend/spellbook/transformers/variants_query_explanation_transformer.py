from lark import Lark, Transformer
from .variants_query_explanations.template_search_explanations import template_search_explanation
from .variants_query_explanations.variant_variants_explanations import variants_explanation
from .variants_query_explanations.card_search_explanations import card_search_explanation
from .variants_query_explanations.card_type_explanations import card_type_explanation
from .variants_query_explanations.card_oracle_explanations import card_oracle_explanation
from .variants_query_explanations.card_keyword_explanations import card_keyword_explanation
from .variants_query_explanations.card_mana_value_explanations import card_mana_value_explanation
from .variants_query_explanations.card_color_explanations import card_color_explanation
from .variants_query_explanations.variant_identity_explanations import identity_explanation
from .variants_query_explanations.variant_prerequisites_explanations import prerequisites_explanation
from .variants_query_explanations.variant_description_explanations import description_explanation
from .variants_query_explanations.results_explanations import results_explanation
from .variants_query_explanations.variant_id_explanations import id_explanation
from .variants_query_explanations.tags_explanations import tag_explanation
from .variants_query_explanations.commander_search_explanations import commander_explanation
from .variants_query_explanations.variant_legality_explanations import legality_explanation
from .variants_query_explanations.variant_price_explanations import price_explanation
from .variants_query_explanations.variant_popularity_explanations import popularity_explanation
from .variants_query_explanations.bracket_explanations import bracket_explanation
from .variants_query_explanations.base import Explanation, Junction, QueryValue, combine, sentence
from .query_parsing import parse_query
from ..parsers.variants_query_grammar import VARIANTS_QUERY_GRAMMAR


class VariantsQueryExplanationTransformer(Transformer):
    '''Turns a search query into the same shape of tree the filtering transformer builds, except
    that each term becomes a phrase describing what it asks for instead of a database condition.'''

    # region explanations
    def card_search_shortcut(self, values):
        q = QueryValue.from_short_string(values[0], key='card', operator=':')
        return card_search_explanation(q)

    def card_search(self, values):
        q = QueryValue.from_string(values[0])
        return card_search_explanation(q)

    def template_search(self, values):
        q = QueryValue.from_string(values[0])
        return template_search_explanation(q)

    def card_type_search(self, values):
        q = QueryValue.from_string(values[0])
        return card_type_explanation(q)

    def card_oracle_search(self, values):
        q = QueryValue.from_string(values[0])
        return card_oracle_explanation(q)

    def card_keyword_search(self, values):
        q = QueryValue.from_string(values[0])
        return card_keyword_explanation(q)

    def card_mana_value_search(self, values):
        q = QueryValue.from_string(values[0])
        return card_mana_value_explanation(q)

    def card_color_search(self, values):
        q = QueryValue.from_string(values[0])
        return card_color_explanation(q)

    def identity_search(self, values):
        q = QueryValue.from_string(values[0])
        return identity_explanation(q)

    def prerequisites_search(self, values):
        q = QueryValue.from_string(values[0])
        return prerequisites_explanation(q)

    def steps_search(self, values):
        q = QueryValue.from_string(values[0])
        return description_explanation(q)

    def results_search(self, values):
        q = QueryValue.from_string(values[0])
        return results_explanation(q)

    def spellbook_id_search(self, values):
        q = QueryValue.from_string(values[0])
        return id_explanation(q)

    def tag_search(self, values):
        q = QueryValue.from_string(values[0])
        return tag_explanation(q)

    def commander_search(self, values):
        q = QueryValue.from_string(values[0])
        return commander_explanation(q)

    def legality_search(self, values):
        q = QueryValue.from_string(values[0])
        return legality_explanation(q)

    def price_search(self, values):
        q = QueryValue.from_string(values[0])
        return price_explanation(q)

    def popularity_search(self, values):
        q = QueryValue.from_string(values[0])
        return popularity_explanation(q)

    def variants_search(self, values):
        q = QueryValue.from_string(values[0])
        return variants_explanation(q)

    def bracket_search(self, values):
        q = QueryValue.from_string(values[0])
        return bracket_explanation(q)
    # endregion

    # region composition
    def factor(self, values):
        match values[0]:
            case '-':
                return values[1].negate()
            case _:
                return values[1]

    def term(self, values):
        return combine(values[0], values[-1], conjunction=True)

    def expression(self, values):
        return combine(values[0], values[-1], conjunction=False)

    def start(self, values):
        if not values:
            return Junction()
        return values[0]
    # endregion


PARSER = Lark(VARIANTS_QUERY_GRAMMAR, parser='lalr', transformer=VariantsQueryExplanationTransformer())


def variants_query_explainer(query_string: str) -> str:
    explanation: Explanation = parse_query(PARSER, query_string)
    return sentence(explanation)
