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
                raise Exception(f'Combo {combo.id} is not satisfiable: {str(combo)}')
        result.append([Card.objects.get(pk=symbol.name) for symbol in model if model[symbol]])
    return result

def find_matching_combos(cards: list[Card]) -> list[Combo]:
    result = []
    cards_symbols = {Symbol(str(card.id)): S.true for card in cards}
    for combo in Combo.objects.all():
        expr = get_expression_from_combo(combo)
        if expr.subs(cards_symbols) == S.true:
            result.append(combo)
    return result

def create_variant(combo: Combo, cards: list[Card]):
    variant = Variant(of=combo, status=Variant.Status.DRAFT)
    variant.save()
    variant.includes.set(cards)
    variant.produces.set(combo.produces.all())
    variant.save()

def update_variants():
    with transaction.atomic():
        print('Updating variants...')
        Variant.objects.all().delete()
        for combo in Combo.objects.all():
            cards = get_cards_for_combo(combo)
            for card_list in cards:
                create_variant(combo, card_list)
        print('Done.')