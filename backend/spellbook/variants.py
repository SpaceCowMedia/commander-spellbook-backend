import hashlib
import logging
from django.db import transaction
from django.conf import settings
from .models import Card, Feature, Combo, Variant
import pulp as lp
logger = logging.getLogger(__name__)


class RecursiveComboException(Exception):
    RECURSION_LIMIT = 20


class LpVariable(lp.LpVariable):
    def __init__(self, name, lowBound=None, upBound=None, cat=..., e=None):
        super().__init__(name, lowBound, upBound, cat, e)
        self.hash = hash(name)


def check_combo_sanity(combo: Combo):
    try:
        get_model_from_combo(combo)
    except RecursiveComboException:
        return False
    return True


def check_feature_sanity(feature: Feature):
    try:
        get_model_from_feature(feature)
    except RecursiveComboException:
        return False
    return True


def extend_model_from_feature(model: lp.LpProblem, feature: Feature, recursive_counter=1) -> lp.LpProblem:
    if recursive_counter > RecursiveComboException.RECURSION_LIMIT:
        raise RecursiveComboException('Recursive combo detected.')
    f = LpVariable(f'F{feature.id}', cat=lp.LpBinary)

    cards_variables = []
    for card in feature.cards.all():
        c = LpVariable(f'C{card.id}', cat=lp.LpBinary)
        cards_variables += c
        model += f - c >= 0

    combo_variables = []
    for combo in feature.produced_by_combos.all():
        b = LpVariable(f'B{combo.id}', cat=lp.LpBinary)
        combo_variables += b
        extend_model_from_combo(model, combo, recursive_counter=recursive_counter + 1)
        model += f - b >= 0

    model += f <= lp.lpSum(cards_variables + combo_variables)
    return model


def extend_model_from_combo(model: lp.LpProblem, combo: Combo, recursive_counter=1) -> lp.LpProblem:
    if recursive_counter > RecursiveComboException.RECURSION_LIMIT:
        raise RecursiveComboException('Recursive combo detected.')
    b = LpVariable(f'B{combo.id}', cat=lp.LpBinary)

    cards_variables = []
    for card in combo.includes.all():
        c = LpVariable(f'C{card.id}', cat=lp.LpBinary)
        cards_variables += c
        model += b - c <= 0

    needed_feature_variables = []
    for feature in combo.needs.all():
        f = LpVariable(f'F{feature.id}', cat=lp.LpBinary)
        needed_feature_variables += f
        extend_model_from_feature(model, feature, recursive_counter=recursive_counter + 1)
        model += b - f <= 0

    model += b - lp.lpSum(cards_variables + needed_feature_variables) + len(cards_variables) + len(needed_feature_variables) - 1 >= 0
    return model


def get_model_from_combo(combo: Combo) -> lp.LpProblem:
    lpmodel = lp.LpProblem(str(combo), lp.LpMinimize)
    extend_model_from_combo(lpmodel, combo)
    lpmodel += LpVariable(f'B{combo.id}', cat=lp.LpBinary) >= 1
    return lpmodel


def get_model_from_feature(feature: Feature) -> lp.LpProblem:
    lpmodel = lp.LpProblem(str(feature), lp.LpMinimize)
    extend_model_from_feature(lpmodel, feature)
    lpmodel += LpVariable(f'F{feature.id}', cat=lp.LpBinary) >= 1
    return lpmodel


def get_cards_for_combo(combo: Combo) -> list[list[Card]]:
    result: list[list[Card]] = list()
    lpmodel = get_model_from_combo(combo)
    lpmodel += lp.lpSum([v for v in lpmodel.variables() if v.name.startswith('C')])
    while lpmodel.status in [lp.LpStatusOptimal, lp.LpStatusNotSolved]:
        for v in lpmodel.variables():
            v.setInitialValue(v.upBound)
        lpmodel.solve(lp.getSolver(settings.PULP_SOLVER, msg=False))
        if lpmodel.status == lp.LpStatusOptimal:
            card_variables = [v for v in lpmodel.variables() if v.name.startswith('C') and v.value() > 0]
            result.append([Card.objects.get(pk=int(v.name[1:])) for v in card_variables])
            lpmodel += lp.lpSum(card_variables) <= len(card_variables) - 1
    return result


def find_included_combos(cards: list[Card]) -> list[Combo]:
    result = []
    card_ids = {str(card.id) for card in cards}
    for combo in Combo.objects.all():
        model = get_model_from_combo(combo)
        variables = [v for v in model.variables() if v.name.startswith('C')]
        variable_names = {v.name[1:] for v in variables}
        if not variable_names.isdisjoint(card_ids):
            for v in variables:
                if v.name[1:] in card_ids:
                    model += v >= 1
                else:
                    model += v <= 0
            for v in model.variables():
                v.setInitialValue(v.upBound)
            model.solve(lp.getSolver(settings.PULP_SOLVER, msg=False))
            if model.status == lp.LpStatusOptimal:
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
    variant.of.set(combos_included)
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
                logger.debug(f'Checking combo [{combo.id}] {combo}...')
                card_list_list = get_cards_for_combo(combo)
                for card_list in card_list_list:
                    unique_id = unique_id_from_cards(card_list)
                    if unique_id not in new_id_set:
                        new_id_set.add(unique_id)
                        if unique_id not in old_id_set:
                            create_variant(card_list, unique_id, combo)
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
