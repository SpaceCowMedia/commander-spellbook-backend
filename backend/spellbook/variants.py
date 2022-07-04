import hashlib
from django.db import transaction
from sympy import Symbol, S, satisfiable
from sympy.logic.boolalg import Exclusive, And, Or
from .models import Card, Feature, Combo, Variant

def get_expression_from_combo(combo: Combo) -> And:
    expression = []
    for card in combo.includes.all():
        expression.append(Symbol(name=str(card.id)))
    for effect in combo.needs.all():
        expression.append(get_expression_from_effect(effect))
    if len(expression) == 0:
            return S.true
    elif len(expression) == 1:
        return expression[0]
    return And(*expression)

def get_expression_from_effect(effect: Feature) -> And:
    expression = []
    for card in Card.objects.filter(features=effect):
        expression.append(Symbol(name=str(card.id)))
    for combo in Combo.objects.filter(produces=effect):
        expression.append(get_expression_from_combo(combo))
    if len(expression) == 0:
        return S.false
    if len(expression) == 1:
        return expression[0]
    return And(Or(*expression), Exclusive(*expression))

def get_cards_for_combo(combo: Combo) -> list[list[Card]]:
    result = []
    for model in satisfiable(get_expression_from_combo(combo), all_models=True):
        if model is False:
            return []
        if model == {True: True}:
            print('Found strange combo', str(combo))
        result.append([Card.objects.get(pk=symbol.name) for symbol in model if model[symbol]])
    return result

def find_included_combos(cards: list[Card]) -> list[int]:
    result = []
    for combo in Combo.objects.all():
        expr = get_expression_from_combo(combo)
        card_ids = {str(card.id) for card in cards}
        cards_symbols = {symbol: symbol.name in card_ids for symbol in expr.free_symbols}
        if expr.subs(cards_symbols) == S.true:
            result.append(combo.id)
    return result

def unique_id_from_cards(cards: list[Card]) -> str:
    hash_algorithm = hashlib.sha256()
    for card in sorted(cards, key=lambda card: card.id):
        hash_algorithm.update(str(card.id).encode('utf-8'))
    return hash_algorithm.hexdigest()

def create_variant(cards: list[Card], unique_id: str, combo: Combo):
    variant = Variant(unique_id=unique_id)
    variant.save()
    variant.includes.set(cards)
    variant.of.add(combo)
    variant.produces.set(
        Combo.objects
        .filter(pk__in=find_included_combos(cards))
        .values_list('produces', flat=True).distinct()
        )
    variant.save()

def generate_variants():
    with transaction.atomic():
        print('Generating variants:')
        print('Fetching all variant unique ids...')
        old_id_set = set(Variant.objects.values_list('unique_id', flat=True))
        new_id_set = set()
        print('Generating new variants...')
        for combo in Combo.objects.all():
            card_list_list = get_cards_for_combo(combo)
            for card_list in card_list_list:
                unique_id = unique_id_from_cards(card_list)
                if unique_id not in new_id_set:
                    new_id_set.add(unique_id)
                    if unique_id not in old_id_set:
                        create_variant(card_list, unique_id)
                else:
                    Variant.objects.get(unique_id=unique_id).of.add(combo)
        to_delete = old_id_set - new_id_set
        added = new_id_set - old_id_set
        print(f'Added {len(added)} new variants.')
        print(f'Deleting {len(to_delete)} variants...')
        Variant.objects.filter(unique_id__in=to_delete).delete()
        print('Done.')
