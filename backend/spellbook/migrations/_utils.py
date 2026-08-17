import re
from collections import defaultdict
from dataclasses import dataclass
from django.db import migrations
from django.db.models import Q
from spellbook.models.ingredient import Ingredient
from spellbook.models.recipe import Recipe
from spellbook.models.utils import CardType, DEFAULT_BATCH_SIZE, strip_accents

FACE_SEPARATOR = ' // '
# words an editor can drop from a card name without changing which card it is
NAME_ARTICLES = frozenset(('the', 'a', 'an'))
# the wording of a starting card state that only repeats the zone the state already belongs to
ZONE_WORDINGS = {Ingredient.CARD_STATE_FIELDS[location]: wording for location, wording in Ingredient.CARD_STATE_ZONE_NAMES.items()}


def populate_name_field(apps, schema_editor):
    Variant = apps.get_model('spellbook', 'Variant')
    Combo = apps.get_model('spellbook', 'Combo')
    VariantSuggestion = apps.get_model('spellbook', 'VariantSuggestion')
    objs = list(Variant.objects.all().only('id', 'name').prefetch_related(
        'cardinvariant_set',
        'templateinvariant_set',
        'featureproducedbyvariant_set',
        'cardinvariant_set__card',
        'templateinvariant_set__template',
        'featureproducedbyvariant_set__feature',
    ).iterator(chunk_size=5000))
    for obj in objs:
        obj.name = Recipe.compute_name(
            cards={c.card.name: c.quantity for c in obj.cardinvariant_set.all()},
            templates={t.template.name: t.quantity for t in obj.templateinvariant_set.all()},
            features_needed={},
            features_produced={f.feature.name: f.quantity for f in obj.featureproducedbyvariant_set.all()},
            features_removed={},
        )
    Variant.objects.bulk_update(objs, ['name'], batch_size=5000)
    objs = list(Combo.objects.all().only('id', 'name').prefetch_related(
        'cardincombo_set',
        'templateincombo_set',
        'featureneededincombo_set',
        'featureproducedincombo_set',
        'featureremovedincombo_set',
        'cardincombo_set__card',
        'templateincombo_set__template',
        'featureneededincombo_set__feature',
        'featureproducedincombo_set__feature',
        'featureremovedincombo_set__feature',
    ).iterator(chunk_size=5000))
    for obj in objs:
        obj.name = Recipe.compute_name(
            cards={c.card.name: c.quantity for c in obj.cardincombo_set.all()},
            templates={t.template.name: t.quantity for t in obj.templateincombo_set.all()},
            features_needed={f.feature.name: f.quantity for f in obj.featureneededincombo_set.all()},
            features_produced={f.feature.name: 1 for f in obj.featureproducedincombo_set.all()},
            features_removed={f.feature.name: 1 for f in obj.featureremovedincombo_set.all()},
        )
    Combo.objects.bulk_update(objs, ['name'], batch_size=5000)
    objs = list(VariantSuggestion.objects.all().only('id', 'name').prefetch_related(
        'uses',
        'requires',
        'produces',
    ).iterator(chunk_size=5000))
    for obj in objs:
        obj.name = Recipe.compute_name(
            cards={c.card: c.quantity for c in obj.uses.all()},
            templates={t.template: t.quantity for t in obj.requires.all()},
            features_needed={},
            features_produced={f.feature: 1 for f in obj.produces.all()},
            features_removed={},
        )
    VariantSuggestion.objects.bulk_update(objs, ['name'], batch_size=5000)


class PopulateNameField(migrations.RunPython):
    def __init__(self) -> None:
        super().__init__(code=populate_name_field, reverse_code=migrations.RunPython.noop)


@dataclass(frozen=True)
class CardStateConversion:
    '''The outcome of reading a face specifier out of a starting card state: either the face it names
    and what the state says once the specifier is taken out of it, or why it could not be read.'''
    used_face: int = 0
    card_state: str = ''
    problem: str = ''


def face_name_candidates(name: str, type_line: str) -> dict[str, set[int]]:
    '''Every way an editor could have written one of the faces of a card, mapped to the 1-based indexes
    of the faces it could mean. Mirrors Card.face_name: the whole face name, plus the short form a
    legendary creature is commonly called by. A form more than one face claims is ambiguous.'''
    card_types = [face_type_line.replace('Time Lord', 'TimeLord').split() for face_type_line in type_line.split(FACE_SEPARATOR)]
    candidates = defaultdict[str, set[int]](set)
    for face, face_name in enumerate(name.split(FACE_SEPARATOR), start=1):
        face_types = set(card_types[face - 1]) if face <= len(card_types) else set()
        candidates[face_name].add(face)
        if ',' in face_name and face_types.issuperset({CardType.LEGENDARY, CardType.CREATURE}):
            candidates[face_name.split(',', 1)[0]].add(face)
    return candidates


def normalized_name(name: str) -> str:
    '''A card name reduced to what an editor could not get wrong: no accents, no case, no punctuation
    and no articles, so that "Heliod, Warped Eclipse" still resolves to "Heliod, the Warped Eclipse".'''
    words = re.sub(r'[^a-z0-9]+', ' ', strip_accents(name).lower()).split()
    return ' '.join(word for word in words if word not in NAME_ARTICLES)


def read_used_face(name: str, type_line: str, zone_wording: str, card_state: str) -> CardStateConversion | None:
    '''Reads out of a starting card state the "as <face>" specifiers editors wrote before the used face
    field existed, returning None when the state holds none of them. Only the faces of that very card
    are looked for, which is what leaves alone the states naming another card, such as "as a copy of X".'''
    candidates = face_name_candidates(name, type_line)
    pattern = re.compile(r'(?:^|\s)as (' + '|'.join(re.escape(candidate) for candidate in sorted(candidates, key=len, reverse=True)) + r')(?=$|[\s.,;:])')
    matches = list(pattern.finditer(card_state))
    if not matches:
        return None
    faces_by_normalized_name = defaultdict[str, set[int]](set)
    for face, face_name in enumerate(name.split(FACE_SEPARATOR), start=1):
        faces_by_normalized_name[normalized_name(face_name)].add(face)
    faces = set[int]()
    # every specifier is taken out, because merging the states of several combos repeats it verbatim
    specifiers = list[tuple[int, int]]()
    for match in matches:
        found = candidates[match.group(1)]
        end = match.end()
        if len(found) > 1:
            # both faces are commonly called the same, so the longest phrase naming exactly one of them
            # decides, forgiving the articles the editor may have left out of it
            tail = card_state[match.start(1):]
            found = set()
            for word in reversed(list(re.finditer(r'\S+', tail))):
                found = faces_by_normalized_name.get(normalized_name(tail[:word.end()]), set())
                if len(found) == 1:
                    end = match.start(1) + word.end()
                    break
            if len(found) != 1:
                return CardStateConversion(problem=f'"{match.group(1)}" names more than one face and no longer phrase names exactly one')
        faces |= found
        specifiers.append((match.start(), end))
    if len(faces) > 1:
        return CardStateConversion(problem=f'names more than one face: {sorted(faces)}')
    remaining = card_state
    for start, end in reversed(specifiers):
        remaining = f'{remaining[:start]} {remaining[end:]}'
    remaining = ' '.join(remaining.split()).strip(' .')
    if remaining.lower().startswith(zone_wording):
        remaining = remaining[len(zone_wording):].strip()
    if remaining.lower().startswith('and '):
        remaining = remaining[len('and '):].strip()
    return CardStateConversion(used_face=faces.pop(), card_state=remaining.strip(' .,'))


def used_face_from_card_states(apps, schema_editor) -> None:
    '''Moves the "as <face>" specifiers editors wrote into the starting card states of multi-faced cards
    into the used face field that now carries them. Variant rows are converted along with the combo rows
    they were rendered from, because a generation only restores the fields of the variants asking for it.'''
    Card = apps.get_model('spellbook', 'Card')
    cards = {card.id: (card.name, card.type_line) for card in Card.objects.filter(name__contains=FACE_SEPARATOR).only('id', 'name', 'type_line')}
    if not cards:
        return
    with_a_card_state = Q()
    for field in ZONE_WORDINGS:
        with_a_card_state |= ~Q(**{field: ''})
    updated_fields = ['used_face', *ZONE_WORDINGS]
    problems = list[str]()
    converted = 0
    for model_name in ('CardInCombo', 'FeatureOfCard', 'CardInVariant'):
        model = apps.get_model('spellbook', model_name)
        to_update = []
        for row in model.objects.filter(with_a_card_state, card_id__in=cards).order_by().only('id', 'card_id', *updated_fields):
            name, type_line = cards[row.card_id]
            changed = False
            for field, zone_wording in ZONE_WORDINGS.items():
                card_state = getattr(row, field)
                conversion = read_used_face(name, type_line, zone_wording, card_state) if card_state else None
                if conversion is None:
                    continue
                if conversion.problem:
                    problems.append(f'{model_name} {row.id}: {field} "{card_state}" {conversion.problem}')
                elif row.used_face is not None and row.used_face != conversion.used_face:
                    problems.append(f'{model_name} {row.id}: {field} "{card_state}" names face {conversion.used_face}, but the row already uses face {row.used_face}')
                else:
                    row.used_face = conversion.used_face
                    setattr(row, field, conversion.card_state)
                    changed = True
            if changed:
                to_update.append(row)
        model.objects.bulk_update(to_update, updated_fields, batch_size=DEFAULT_BATCH_SIZE)
        converted += len(to_update)
    if converted:
        print(f'Moved the used face out of the starting card states of {converted} rows.')
    if problems:
        print(f'{len(problems)} rows were left untouched, for an editor to fix by hand:')
        for problem in problems:
            print(f'  {problem}')
