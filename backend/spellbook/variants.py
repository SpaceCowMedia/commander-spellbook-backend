import hashlib
import logging
from django.db import transaction
from django.db.models import Count
from django.conf import settings
from .models import Card, Feature, Combo, Variant
import pulp as lp
logger = logging.getLogger(__name__)


class RecursiveComboException(Exception):
    RECURSION_LIMIT = 20


class LpVariable(lp.LpVariable):
    def __init__(self, name: str, order: int = 0, lowBound=None, upBound=None, cat=lp.LpContinuous, e=None):
        super().__init__(name, lowBound, upBound, cat, e)
        self.hash = hash(name)
        self.order = order


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
    # The variable representing the feature in the model
    f = LpVariable(f'F{feature.id}', order=recursive_counter, cat=lp.LpBinary)

    cards_variables = []
    for card in feature.cards.all():
        c = LpVariable(f'C{card.id}', order=recursive_counter, cat=lp.LpBinary)
        cards_variables += c
        # For each card having the feature, we need f to be 1 if any of those is 1
        model += f - c >= 0

    combo_variables = []
    for combo in feature.produced_by_combos.all():
        b = LpVariable(f'B{combo.id}', order=recursive_counter, cat=lp.LpBinary)
        combo_variables += b
        # We add the constraints around the combo to the current model
        extend_model_from_combo(model, combo, recursive_counter=recursive_counter + 1)
        # For each combo producing the feature, we need f to be 1 if any of those is 1
        model += f - b >= 0

    # If none of the cards or combos producing the feature are in the model, f is 0
    model += f <= lp.lpSum(cards_variables + combo_variables)
    return model


def extend_model_from_combo(model: lp.LpProblem, combo: Combo, recursive_counter=1) -> lp.LpProblem:
    if recursive_counter > RecursiveComboException.RECURSION_LIMIT:
        raise RecursiveComboException('Recursive combo detected.')
    # The variable representing the combo in the model
    b = LpVariable(f'B{combo.id}', order=recursive_counter, cat=lp.LpBinary)

    cards_variables = []
    for card in combo.includes.all():
        c = LpVariable(f'C{card.id}', order=recursive_counter, cat=lp.LpBinary)
        cards_variables += c
        # For each card included in the combo, we need b to be 0 if any of those is 0
        model += b - c <= 0

    needed_feature_variables = []
    for feature in combo.needs.all():
        f = LpVariable(f'F{feature.id}', order=recursive_counter, cat=lp.LpBinary)
        needed_feature_variables += f
        # We add the constraints around the feature to the current model
        extend_model_from_feature(model, feature, recursive_counter=recursive_counter + 1)
        # For each feature needed by the combo, we need b to be 0 if any of those is 0
        model += b - f <= 0

    # If every card and feature needed by the combo is in the model, b is 1
    model += b - lp.lpSum(cards_variables + needed_feature_variables) + len(cards_variables) + len(needed_feature_variables) - 1 >= 0
    return model


def get_model_from_combo(combo: Combo) -> lp.LpProblem:
    lpmodel = lp.LpProblem(str(combo).replace(' ', '_'), lp.LpMinimize)
    extend_model_from_combo(lpmodel, combo)
    # In order to solve for the comvo, its variable must be 1
    lpmodel += LpVariable(f'B{combo.id}', cat=lp.LpBinary) >= 1
    return lpmodel


def get_model_from_feature(feature: Feature) -> lp.LpProblem:
    lpmodel = lp.LpProblem(str(feature).replace(' ', '_'), lp.LpMinimize)
    extend_model_from_feature(lpmodel, feature)
    # In order to solve for the feature, its variable must be 1
    lpmodel += LpVariable(f'F{feature.id}', cat=lp.LpBinary) >= 1
    return lpmodel


def get_cards_for_combo(combo: Combo) -> list[list[Card]]:
    result: list[list[Card]] = list()
    lpmodel = get_model_from_combo(combo)
    lpmodel += lp.lpSum([v for v in lpmodel.variables() if v.name.startswith('C')])
    while lpmodel.status in {lp.LpStatusOptimal, lp.LpStatusNotSolved}:
        # We need to set initial values to 1 to avoid None values in the solution
        for v in lpmodel.variables():
            v.setInitialValue(v.upBound)
        lpmodel.solve(lp.getSolver(settings.PULP_SOLVER, msg=False))
        if lpmodel.status == lp.LpStatusOptimal:
            # Selecting only card variables with a value of 1
            card_variables = [v for v in lpmodel.variables() if v.name.startswith('C') and v.value() > 0]
            # Fetching the cards from the db, ordered by depth of first encounter
            result.append([Card.objects.get(pk=int(v.name[1:])) for v in sorted(card_variables, key=lambda v: v.order)])
            # Eclude any solution containing the current variant of the combo
            lpmodel += lp.lpSum(card_variables) <= len(card_variables) - 1
    return result


def find_included_combos(cards: list[Card]) -> list[Combo]:
    result = []
    card_ids = {str(card.id) for card in cards}
    for combo in Combo.objects.all():
        model = get_model_from_combo(combo)
        variables = [v for v in model.variables() if v.name.startswith('C')]
        variable_names = {v.name[1:] for v in variables}
        # Check if combo has something in common with the cards
        if not variable_names.isdisjoint(card_ids):
            for v in variables:
                if v.name[1:] in card_ids:
                    # Cards in list are set to 1
                    model += v >= 1
                else:
                    # Cards not in list are set to 0
                    model += v <= 0
            # We need to set initial values to 1 to avoid None values in the solution
            for v in model.variables():
                v.setInitialValue(v.upBound)
            model.solve(lp.getSolver(settings.PULP_SOLVER, msg=False))
            # If model can be solved, the card list contains the combo
            if model.status == lp.LpStatusOptimal:
                result.append(combo)
    return result


def unique_id_from_cards(cards: list[Card]) -> str:
    hash_algorithm = hashlib.sha256()
    for card in sorted(cards, key=lambda card: card.id):
        hash_algorithm.update(str(card.id).encode('utf-8'))
    return hash_algorithm.hexdigest()


def update_variant(cards: list[Card], unique_id: str, combo: Combo):
    variant = Variant.objects.get(unique_id=unique_id)
    combos_included = find_included_combos(cards)
    variant.of.set(combos_included)
    variant.produces.set(
        Combo.objects
        .filter(pk__in=[c.id for c in combos_included])
        .values_list('produces', flat=True).distinct()
    )


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
        .values_list('produces', flat=True)
        .distinct()
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
        for combo in Combo.objects.annotate(m=Count('needs') + Count('includes')).filter(m__gt=1):
            try:
                logger.debug(f'Checking combo [{combo.id}] {combo}...')
                card_list_list = get_cards_for_combo(combo)
                for card_list in card_list_list:
                    unique_id = unique_id_from_cards(card_list)
                    if unique_id not in new_id_set:
                        new_id_set.add(unique_id)
                        if unique_id in old_id_set:
                            update_variant(card_list, unique_id, combo)
                        else:
                            create_variant(card_list, unique_id, combo)
            except RecursiveComboException:
                logger.warning(f'Recursive combo (id: {combo.id}) detected. Aborting variant generation.')
                raise
        to_delete = old_id_set - new_id_set
        added = new_id_set - old_id_set
        updated = new_id_set & old_id_set
        logger.info(f'Added {len(added)} new variants.')
        logger.info(f'Updated {len(updated)} variants.')
        logger.info(f'Deleting {len(to_delete)} variants...')
        Variant.objects.filter(unique_id__in=to_delete).delete()
        logger.info('Done.')
        return len(added), len(updated), len(to_delete) + restored
