import hashlib
import logging
from django.db import transaction
from sympy import Symbol, S, satisfiable
from sympy.logic.boolalg import Exclusive, And, Or
from .models import Card, Feature, Combo, Variant
logger = logging.getLogger(__name__)


class RecursiveComboException(Exception):
    RECURSION_LIMIT = 20


class OrderedSymbol(Symbol):
    def __new__(cls, name, order=0):
        obj = Symbol.__new__(cls, name)
        obj.order = order
        return obj


def get_expression_from_combo(combo: Combo, recursion_counter: int = 1) -> And:
    if recursion_counter > RecursiveComboException.RECURSION_LIMIT:
        raise RecursiveComboException('Recursive combo detected.')
    expression = []
    for card in combo.includes.all():
        expression.append(OrderedSymbol(name=str(card.id), order=recursion_counter))
    for effect in combo.needs.all():
        expression.append(get_expression_from_effect(effect, recursion_counter=recursion_counter + 1))
    if len(expression) == 0:
        return S.true
    if len(expression) == 1:
        return expression[0]
    return And(*expression)


def get_expression_from_effect(effect: Feature, recursion_counter: int = 1) -> And:
    if recursion_counter > RecursiveComboException.RECURSION_LIMIT:
        raise RecursiveComboException('Recursive combo detected.')
    expression = []
    for card in effect.cards.all():
        expression.append(OrderedSymbol(name=str(card.id), order=recursion_counter))
    for combo in effect.produced_by_combos.all():
        expression.append(get_expression_from_combo(combo, recursion_counter=recursion_counter + 1))
    if len(expression) == 0:
        return S.false
    if len(expression) == 1:
        return expression[0]
    return Or(*expression)


def check_combo_sanity(combo: Combo):
    try:
        get_expression_from_combo(combo)
    except RecursiveComboException:
        return False
    return True


def check_feature_sanity(feature: Feature):
    try:
        get_expression_from_effect(feature)
    except RecursiveComboException:
        return False
    return True


def get_cards_for_combo(combo: Combo) -> list[list[Card]]:
    result: list[list[Card]] = list()
    expr = get_expression_from_combo(combo)
    for model in satisfiable(expr, all_models=True):
        if model is False:
            return []
        if model == {True: True}:
            logger.info('Found strange combo', str(combo))
            continue
        # Check minimality of solution
        if all([expr.subs({s: s != symbol and model[s] for s in model}) == S.false for symbol in model if model[symbol]]):
            result.append([Card.objects.get(pk=symbol.name) for symbol in sorted(model, key=lambda os: os.order) if model[symbol]])
    return result


def find_included_combos(cards: list[Card]) -> list[Combo]:
    result = []
    for combo in Combo.objects.all():
        expr = get_expression_from_combo(combo)
        card_ids = {str(card.id) for card in cards}
        cards_symbols = {symbol: symbol.name in card_ids for symbol in expr.free_symbols}
        if expr.subs(cards_symbols) == S.true:
            result.append(combo)
    return result


def unique_id_from_cards(cards: list[Card]) -> str:
    hash_algorithm = hashlib.sha256()
    for card in sorted(cards, key=lambda card: card.id):
        hash_algorithm.update(str(card.id).encode('utf-8'))
    return hash_algorithm.hexdigest()


def create_variant(cards: list[Card], unique_id: str, combo: Combo):
    combos_included = find_included_combos(cards)
    prerequisites = '\n'.join(c.prerequisites for c in combos_included)
    description = '\n'.join(c.description for c in combos_included)
    variant = Variant(unique_id=unique_id, prerequisites=prerequisites, description=description)
    variant.save()
    variant.includes.set(cards)
    variant.of.add(combo)
    variant.produces.set(
        Combo.objects
        .filter(pk__in=[c.id for c in combos_included])
        .values_list('produces', flat=True).distinct()
    )


def generate_variants() -> tuple[int, int]:
    with transaction.atomic():
        logger.info('Deleting variants set to RESTORE...')
        _, deleted_dict = Variant.objects.filter(status=Variant.Status.RESTORE).delete()
        restored = deleted_dict['spellbook.Variant'] if 'spellbook.Variant' in deleted_dict else 0
        logger.info(f'Deleted {restored} variants set to RESTORE.')
        logger.info('Generating variants:')
        logger.info('Fetching all variant unique ids...')
        old_id_set = set(Variant.objects.values_list('unique_id', flat=True))
        new_id_set = set()
        logger.info('Generating new variants...')
        for combo in Combo.objects.all():
            try:
                card_list_list = get_cards_for_combo(combo)
                for card_list in card_list_list:
                    unique_id = unique_id_from_cards(card_list)
                    if unique_id not in new_id_set:
                        new_id_set.add(unique_id)
                        if unique_id not in old_id_set:
                            create_variant(card_list, unique_id, combo)
                    else:
                        Variant.objects.get(unique_id=unique_id).of.add(combo)
            except RecursiveComboException:
                logger.warning(f'Recursive combo (id: {combo.id}) detected. Aborting variant generation.')
                raise
        to_delete = old_id_set - new_id_set
        added = new_id_set - old_id_set
        logger.info(f'Added {len(added)} new variants.')
        logger.info(f'Deleting {len(to_delete)} variants...')
        Variant.objects.filter(unique_id__in=to_delete).delete()
        logger.info('Done.')
        return len(added), len(to_delete) + restored
