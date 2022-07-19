from dataclasses import dataclass
import hashlib
from itertools import starmap
import json
import logging
from multiprocessing.dummy import Pool as ThreadPool
from django.db import transaction
from django.db.models import Count
from django.conf import settings
import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition
from .models import Card, Feature, Combo, Variant
logging.getLogger('pyomo.opt').setLevel(logging.WARNING)
logging.getLogger('pyomo.core').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


RECURSION_LIMIT = 20

def unique_id_from_cards_ids(cards: list[int]) -> str:
    hash_algorithm = hashlib.sha256()
    hash_algorithm.update(json.dumps(sorted(cards)).encode('utf-8'))
    return hash_algorithm.hexdigest()


def priority_dict_for_combo(combo: Combo, recursion_counter=0) -> dict[int, int]:
    if recursion_counter > RECURSION_LIMIT:
        raise Exception('Recursion limit reached with combo {}'.format(combo.id))
    result = dict[int, int]()
    for card in combo.includes.all():
        result[card.id] = recursion_counter
    for feature in combo.needs.all():
        for card in feature.cards.all():
            result[card.id] = recursion_counter + 1
        for combo in feature.produced_by_combos.all():
            p1 = priority_dict_for_combo(combo, recursion_counter + 2)
            result = p1 | result
    return result


def check_combo_sanity(combo: Combo, recursion_counter: int = 0) -> bool:
    if recursion_counter > RECURSION_LIMIT:
        return False
    for feature in combo.needs.all():
        for combo in feature.produced_by_combos.all():
            if not check_combo_sanity(combo, recursion_counter + 1):
                return False
    return True


def update_variant(unique_id: str, combos_included: list[int], features: list[int]):
    variant = Variant.objects.get(unique_id=unique_id)
    variant.of.set(combos_included)
    variant.produces.set(features)


def create_variant(cards: list[Card], unique_id: str, combos_included: list[int], features: list[int]):
    combos = Combo.objects.filter(id__in=combos_included)
    prerequisites = '\n'.join(c.prerequisites for c in combos)
    description = '\n'.join(c.description for c in combos)
    variant = Variant(unique_id=unique_id, prerequisites=prerequisites, description=description)
    variant.save()
    variant.includes.set(cards)
    variant.of.set(combos_included)
    variant.produces.set(features)


def base_model() -> pyo.ConcreteModel:
    model = pyo.ConcreteModel(name='Spellbook')
    combos = Combo.objects.all()
    features = Feature.objects.all()
    cards = Card.objects.all()
    model.B = pyo.Set(initialize=combos.values_list('id', flat=True))
    model.F = pyo.Set(initialize=features.values_list('id', flat=True))
    model.C = pyo.Set(initialize=cards.values_list('id', flat=True))
    model.b = pyo.Var(model.B, domain=pyo.Boolean)
    model.f = pyo.Var(model.F, domain=pyo.Boolean)
    model.c = pyo.Var(model.C, domain=pyo.Boolean)
    # Combo constraints
    model.BC = pyo.ConstraintList()
    model.BF = pyo.ConstraintList()
    model.BCF = pyo.ConstraintList()
    for combo in combos:
        b = model.b[combo.id]
        included = combo.includes.all()
        card_vars = []
        for card in included:
            c = model.c[card.id]
            card_vars.append(c)
            model.BC.add(b <= c)
        needed = combo.needs.all()
        feature_vars = []
        for feature in needed:
            f = model.f[feature.id]
            feature_vars.append(f)
            model.BF.add(b <= f)
        model.BCF.add(b >= sum(card_vars + feature_vars) - len(card_vars) - len(feature_vars) + 1)
    # Feature constraints
    model.FC = pyo.ConstraintList()
    model.FB = pyo.ConstraintList()
    model.FCB = pyo.ConstraintList()
    for feature in features:
        f = model.f[feature.id]
        cards = feature.cards.all()
        card_vars = []
        for card in cards:
            c = model.c[card.id]
            card_vars.append(c)
            model.FC.add(f >= c)
        combo_vars = []
        for combo in feature.produced_by_combos.all():
            b = model.b[combo.id]
            combo_vars.append(b)
            model.FB.add(f >= b)
        model.FCB.add(f <= sum(card_vars + combo_vars))
    # Minimize cards, maximize features
    model.MinimizeCards = pyo.Objective(expr=sum(model.c[i] for i in model.c), sense=pyo.minimize)
    model.MinimizeCards.deactivate()
    model.MaximizeFeatures = pyo.Objective(expr=sum(model.f[i] for i in model.f), sense=pyo.maximize)
    model.MaximizeFeatures.deactivate()
    model.MaximizeCombos = pyo.Objective(expr=sum(model.b[i] for i in model.b), sense=pyo.maximize)
    model.MaximizeCombos.deactivate()
    model.Sequential = pyo.ConstraintList()
    model.Variants = pyo.ConstraintList()
    return model


def combo_model(base_model: pyo.ConcreteModel, combo: Combo) -> pyo.ConcreteModel:
    model = base_model.clone()
    model.XB = pyo.Constraint(expr=model.b[combo.id] >= 1)
    return model


@dataclass
class VariantDefinition:
    card_ids: list[int]
    combo_ids: list[int]
    feature_ids: list[int]


def get_variants_from_model(base_model: pyo.ConcreteModel) -> dict[str, VariantDefinition]:
    def variants_from_combo(model: pyo.ConcreteModel, opt: pyo.SolverFactory, priorityc: dict[Card, int]) -> dict[str, VariantDefinition]:
        result: dict[str, VariantDefinition] = {}
        while True:
            if solve_combo_model(model, opt):
                # Selecting only variables with a value of 1
                card_id_list = sorted([v for v in model.c if model.c[v].value == 1], key=lambda c: priorityc[c])
                feature_id_list = [v for v in model.f if model.f[v].value == 1]
                combo_id_list = [v for v in model.b if model.b[v].value == 1]
                unique_id = unique_id_from_cards_ids(card_id_list)
                result[unique_id] = VariantDefinition(card_ids=card_id_list, combo_ids=combo_id_list, feature_ids=feature_id_list)
                # Eclude any solution containing the current variant of the combo, from now on
                model.Variants.add(sum(model.c[i] for i in card_id_list) <= len(card_id_list) - 1)
            else:
                break
        return result
    # logging.info(f'Spawning thread pool of size {settings.PARALLEL_SOLVERS}...')
    # pool = ThreadPool(processes=settings.PARALLEL_SOLVERS)
    logging.info(f'Computing all possible variants')
    # Considering only combos with two or more components to avoid 1 -> 1 combos
    opt = pyo.SolverFactory('glpk', executable='D:\Downloads\winglpk-4.65\glpk-4.65\w64\glpsol.exe')
    results = list(starmap(variants_from_combo,
        ((combo_model(base_model, c), opt, priority_dict_for_combo(c)) for c in
            Combo.objects.annotate(m=Count('needs') + Count('includes')).filter(m__gt=1))))
    logging.info(f'Merging results, discarding duplicates...')
    result = {}
    for r in results:
        result.update(r)
    # pool.close()
    logging.info(f'Done: pool closed.')
    return result


def solve_combo_model(model: pyo.ConcreteModel, opt: pyo.SolverFactory) -> bool:
    model.MinimizeCards.activate()
    results = opt.solve(model, tee=False)
    if results.solver.termination_condition == TerminationCondition.optimal:
        model.Sequential.add(model.MinimizeCards <= pyo.value(model.MinimizeCards))
        model.MinimizeCards.deactivate()
        model.MaximizeFeatures.activate()
        results = opt.solve(model, tee=False)
        if results.solver.termination_condition == TerminationCondition.optimal:
            model.Sequential.add(model.MaximizeFeatures >= pyo.value(model.MaximizeFeatures))
            model.MaximizeFeatures.deactivate()
            model.MaximizeCombos.activate()
            results = opt.solve(model, tee=False)
            if results.solver.termination_condition == TerminationCondition.optimal:
                model.Sequential.clear()
                model.MaximizeCombos.deactivate()
                return True
    model.MinimizeCards.deactivate()
    model.MaximizeFeatures.deactivate()
    model.MaximizeCombos.deactivate()
    return False

def generate_variants() -> tuple[int, int]:
    with transaction.atomic():
        logger.info('Deleting variants set to RESTORE...')
        _, deleted_dict = Variant.objects.filter(status=Variant.Status.RESTORE).delete()
        restored = deleted_dict['spellbook.Variant'] if 'spellbook.Variant' in deleted_dict else 0
        logger.info(f'Deleted {restored} variants set to RESTORE.')
        logger.info('Fetching all variant unique ids...')
        old_id_set = set(Variant.objects.values_list('unique_id', flat=True))
        logger.info('Computing combos MILP representation...')
        model = base_model()
        logger.info('Solving MILP for each combo...')
        variants = get_variants_from_model(model)
        logger.info('Saving variants...')
        for unique_id, variant_def in variants.items():
            if unique_id in old_id_set:
                update_variant(unique_id, variant_def.combo_ids, variant_def.feature_ids)
            else:
                create_variant(variant_def.card_ids, unique_id, variant_def.combo_ids, variant_def.feature_ids)
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
