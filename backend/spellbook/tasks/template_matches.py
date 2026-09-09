from collections import defaultdict
from django.db.models import QuerySet
from spellbook.models import Card, Template, TemplateMatch, DEFAULT_BATCH_SIZE
from spellbook.transformers.scryfall_query_transformer import scryfall_query_parser


def matching_card_ids(template: Template) -> set[int]:
    '''The cards a template stands for.

    A query is read as naming a card that could be played in the combo asking for the template, so it
    is narrowed to what Commander allows, the way the link an editor clicks on is; a replacement list
    is taken exactly as the editor wrote it.'''
    if template.scryfall_query:
        return set(
            Card.objects
            .filter(scryfall_query_parser(template.scryfall_query), legal_commander=True)
            .order_by()
            .values_list('pk', flat=True)
        )
    return set(template.replacements.order_by().values_list('pk', flat=True))


def update_template_matches(templates: QuerySet[Template] | None = None, log_error=lambda t: print(t)) -> tuple[int, int]:
    '''Rewrites what the given templates stand for, returning how many matches were added and removed.

    A template whose query cannot be read keeps the matches it had, so that one unreadable query does
    not empty a template out from under the combos using it.'''
    if templates is None:
        templates = Template.objects.all()
    templates = templates.order_by()
    wanted = set[tuple[int, int]]()
    covered = list[int]()
    for template in templates:
        try:
            card_ids = matching_card_ids(template)
        except Exception as e:
            log_error(f'Template {template.name} has a query that cannot be read: {e}')
            continue
        covered.append(template.pk)
        wanted.update((card_id, template.pk) for card_id in card_ids)
    known = set[tuple[int, int]](
        TemplateMatch.objects.filter(template_id__in=covered).order_by().values_list('card_id', 'template_id')
    )
    added = wanted - known
    removed = known - wanted
    TemplateMatch.objects.bulk_create(
        [TemplateMatch(card_id=card_id, template_id=template_id) for card_id, template_id in added],
        batch_size=DEFAULT_BATCH_SIZE,
    )
    removed_by_template = defaultdict[int, list[int]](list)
    for card_id, template_id in removed:
        removed_by_template[template_id].append(card_id)
    for template_id, card_ids in removed_by_template.items():
        for start in range(0, len(card_ids), DEFAULT_BATCH_SIZE):
            TemplateMatch.objects.filter(template_id=template_id, card_id__in=card_ids[start:start + DEFAULT_BATCH_SIZE]).delete()
    return len(added), len(removed)
