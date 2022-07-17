import hashlib
import json
import logging
import pulp as lp
from multiprocessing.dummy import Pool as ThreadPool
from django.db import transaction
from django.db.models import Count
from django.conf import settings

from .pulp_patch import LpProblem
from .models import Card, Feature, Combo, Variant
from copy import deepcopy
logger = logging.getLogger(__name__)


RECURSION_LIMIT = 20


class LpProblemFactory():
    def __init__(self, constraints: list = [], variables: dict[str, lp.LpVariable] = {}):
        self.constraints = constraints
        self.variables = variables

    def __iadd__(self, constraint):
        self.constraints.append(constraint)
        return self

    def __getitem__(self, key):
        if key in self.variables:
            return self.variables[key]
        self.variables[key] = lp.LpVariable(name=key, cat=lp.LpBinary)
        return self.variables[key]

    def to_pulp(self, name: str) -> lp.LpProblem:
        p = LpProblem(name.replace(' ', '_'), lp.LpMinimize)
        for constraint in self.constraints:
            p += constraint
        return p

    def copy(self):
        return LpProblemFactory(deepcopy(self.constraints), deepcopy(self.variables))


def extend_model_from_feature(model: LpProblemFactory, feature: Feature):
    # The variable representing the feature in the model
    f = model[f'F{feature.id}']

    card_variables = []
    for card in feature.cards.all():
        c = model[f'C{card.id}']
        card_variables += c
        # For each card that has the feature, we need f to be 1 if any of those is 1
        model += f - c >= 0

    combo_variables = []
    for combo in feature.produced_by_combos.all():
        b = model[f'B{combo.id}']
        combo_variables += b
        # For each combo producing the feature, we need f to be 1 if any of those is 1
        model += f - b >= 0

    # If none of the cards or combos producing the feature are in the model, f is 0
    model += f <= lp.lpSum(card_variables + combo_variables)


def extend_model_from_combo(model: LpProblemFactory, combo: Combo):
    # The variable representing the combo in the model
    b = model[f'B{combo.id}']

    cards_variables = []
    for card in combo.includes.all():
        c = model[f'C{card.id}']
        cards_variables += c
        # For each card included in the combo, we need b to be 0 if any of those is 0
        model += b - c <= 0

    needed_feature_variables = []
    for feature in combo.needs.all():
        f = model[f'F{feature.id}']
        needed_feature_variables += f
        # For each feature needed by the combo, we need b to be 0 if any of those is 0
        model += b - f <= 0

    # If every card and feature needed by the combo is in the model, b is 1
    model += b - lp.lpSum(cards_variables + needed_feature_variables) + len(cards_variables) + len(needed_feature_variables) - 1 >= 0


def unique_id_from_cards(cards: list[Card]) -> str:
    hash_algorithm = hashlib.sha256()
    hash_algorithm.update(json.dumps(sorted(map(lambda card: card.id, cards))).encode('utf-8'))
    return hash_algorithm.hexdigest()


def priority_dict_for_combo(combo: Combo, recursion_counter=0) -> tuple[dict[Card, int], dict[Feature, int]]:
    if recursion_counter > RECURSION_LIMIT:
        raise Exception('Recursion limit reached with combo {}'.format(combo.id))
    result = dict[Card, int]()
    result2 = dict[Feature, int]()
    for card in combo.includes.all():
        result[card] = recursion_counter
    for feature in combo.produces.all():
        result2[feature] = recursion_counter
    for feature in combo.needs.all():
        result2[feature] = recursion_counter + 1
        for card in feature.cards.all():
            result[card] = recursion_counter + 1
        for combo in feature.produced_by_combos.all():
            p1, p2 = priority_dict_for_combo(combo, recursion_counter + 2)
            result = p1 | result
            result2 = p2 | result2
    return result, result2


def check_combo_sanity(combo: Combo, recursion_counter: int = 0) -> bool:
    if recursion_counter > RECURSION_LIMIT:
        return False
    for feature in combo.needs.all():
        for combo in feature.produced_by_combos.all():
            if not check_combo_sanity(combo, recursion_counter + 1):
                return False
    return True


def get_variants_from_model(base_model: LpProblemFactory) -> dict[str, tuple[list[Card], list[Combo], list[Feature]]]:
    def variants_from_combo(combo: Combo, model: LpProblemFactory) -> dict[str, tuple[list[Card], list[Combo], list[Feature]]]:
        result: dict[str, tuple[list[Card], list[Feature]]] = {}
        priorityc, priorityf = priority_dict_for_combo(combo)
        lpmodel = model.to_pulp(f'P{combo.id}')
        # Minimize cards, maximize features
        lpmodel.addConstraint(model[f'B{combo.id}'] >= 1)
        while lpmodel.status in {lp.LpStatusOptimal, lp.LpStatusNotSolved}:
            # We need to set initial values to 1 to avoid None values in the solution
            for v in lpmodel.variables():
                v.setInitialValue(v.upBound)
            # Minimize cards, maximize features
            try:
                lpmodel.sequentialSolve(objectives=[
                    lp.lpSum([v for v in lpmodel.variables() if v.name.startswith('C')]),
                    -lp.lpSum([v for v in lpmodel.variables() if v.name.startswith('F')]),
                    lp.lpSum([v for v in lpmodel.variables() if v.name.startswith('B')])
                ],
                    solver=lp.getSolver(settings.PULP_SOLVER, msg=settings.PULP_DEBUG))
            except lp.PulpSolverError:
                logging.error(lpmodel)
                raise

            if lpmodel.status == lp.LpStatusOptimal:
                # Selecting only variables with a value of 1
                not_none_variables = [v for v in lpmodel.variables() if v.value() is not None]
                card_variables = [v for v in not_none_variables if v.name.startswith('C') and v.value() > 0]
                feature_variables = [v for v in not_none_variables if v.name.startswith('F') and v.value() > 0]
                combo_variables = [v for v in not_none_variables if v.name.startswith('B') and v.value() > 0]
                # Fetching the cards from the db, ordered by depth of first encounter
                card_list = [Card.objects.get(pk=int(v.name[1:])) for v in card_variables]
                unique_id = unique_id_from_cards(card_list)
                if unique_id not in result:
                    combo_list = [Combo.objects.get(pk=int(v.name[1:])) for v in combo_variables]
                    feature_list = sorted([Feature.objects.get(pk=int(v.name[1:])) for v in feature_variables], key=lambda f: priorityf.get(f, RECURSION_LIMIT))
                    card_list = sorted(card_list, key=lambda card: priorityc[card])
                    result[unique_id] = (card_list, feature_list, combo_list)
                # Eclude any solution containing the current variant of the combo, from now on
                model += lp.lpSum(card_variables) <= len(card_variables) - 1
                lpmodel = model.to_pulp(f'P{combo.id}')
                lpmodel.addConstraint(model[f'B{combo.id}'] >= 1)
        return result
    logging.info(f'Spawning thread pool of size {settings.PULP_THREADS}...')
    pool = ThreadPool(processes=settings.PULP_THREADS)
    # Considering only combos with two or more components to avoid 1 -> 1 combos
    result = {}
    results = pool.starmap(variants_from_combo,
        ((c, base_model.copy()) for c in
            Combo.objects.annotate(m=Count('needs') + Count('includes')).filter(m__gt=1)))
    for r in results:
        result.update(r)
    pool.close()
    return result


def update_variant(unique_id: str, combos_included: list[Combo], features: list[Feature]):
    variant = Variant.objects.get(unique_id=unique_id)
    variant.of.set(combos_included)
    variant.produces.set(features)


def create_variant(cards: list[Card], unique_id: str, combos_included: list[Combo], features: list[Feature]):
    prerequisites = '\n'.join(c.prerequisites for c in combos_included)
    description = '\n'.join(c.description for c in combos_included)
    variant = Variant(unique_id=unique_id, prerequisites=prerequisites, description=description)
    variant.save()
    variant.includes.set(cards)
    variant.of.set(combos_included)
    variant.produces.set(features)


def generate_variants() -> tuple[int, int]:
    with transaction.atomic():
        logger.info('Deleting variants set to RESTORE...')
        _, deleted_dict = Variant.objects.filter(status=Variant.Status.RESTORE).delete()
        restored = deleted_dict['spellbook.Variant'] if 'spellbook.Variant' in deleted_dict else 0
        logger.info(f'Deleted {restored} variants set to RESTORE.')
        logger.info('Fetching all variant unique ids...')
        old_id_set = set(Variant.objects.values_list('unique_id', flat=True))
        logger.info('Computing combos MILP representation...')
        model = LpProblemFactory()
        for combo in Combo.objects.all():
            extend_model_from_combo(model, combo)
        for feature in Feature.objects.all():
            extend_model_from_feature(model, feature)
        logger.info('Solving MILP for each combo...')
        variants = get_variants_from_model(model)
        logger.info('Saving variants...')
        for unique_id, (cards, features, combos) in variants.items():
            if unique_id in old_id_set:
                update_variant(unique_id, combos, features)
            else:
                create_variant(cards, unique_id, combos, features)
        new_id_set = set(variants.keys())
        to_delete = old_id_set - new_id_set
        added = new_id_set - old_id_set
        updated = new_id_set & old_id_set
        logger.info(f'Added {len(added)} new variants.')
        logger.info(f'Updated {len(updated)} variants.')
        logger.info(f'Deleting {len(to_delete)} variants...')
        Variant.objects.filter(unique_id__in=to_delete).delete()
        logger.info('Done.')
        return len(added), len(updated), len(to_delete) + restored
