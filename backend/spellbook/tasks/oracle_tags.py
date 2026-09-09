from collections import defaultdict
from uuid import UUID
from spellbook.models import Card, CardOracleTag, OracleTag, OracleTagName, DEFAULT_BATCH_SIZE, oracle_tag_key
from .scryfall import Scryfall


def update_oracle_tags(scryfall: Scryfall) -> tuple[int, int]:
    '''Rewrites the oracle tags and what they are on, returning how many joins were added and removed.

    The joins are written with the hierarchy already resolved, so that asking for a tag never has to walk
    down to the tags below it. Both sides are diffed rather than rebuilt, because the tags barely move
    between one sync and the next while the joins number in the hundreds of thousands.'''
    OracleTag.objects.bulk_create(
        [
            OracleTag(id=tag['id'], slug=tag['slug'], label=tag.get('label') or '', description=tag.get('description') or '')
            for tag in scryfall.tags
        ],
        update_conflicts=True,
        unique_fields=['id'],
        update_fields=['slug', 'label', 'description'],
        batch_size=DEFAULT_BATCH_SIZE,
    )
    OracleTag.objects.exclude(pk__in=[tag['id'] for tag in scryfall.tags]).delete()

    names = dict[str, tuple[str, str]]()
    for tag in scryfall.tags:
        for name in (tag['slug'], *tag['aliases']):
            names.setdefault(oracle_tag_key(name), (name, tag['id']))
    OracleTagName.objects.exclude(normalized_name__in=names).delete()
    OracleTagName.objects.bulk_create(
        [OracleTagName(tag_id=tag_id, name=name, normalized_name=key) for key, (name, tag_id) in names.items()],
        update_conflicts=True,
        unique_fields=['normalized_name'],
        update_fields=['name', 'tag'],
        batch_size=DEFAULT_BATCH_SIZE,
    )

    card_ids = {
        str(oracle_id): card_id
        for oracle_id, card_id in Card.objects.exclude(oracle_id=None).order_by().values_list('oracle_id', 'pk')
    }
    wanted = {
        (card_ids[oracle_id], tag_id)
        for tag_id, oracle_ids in scryfall.taggings.items()
        for oracle_id in oracle_ids
        if oracle_id in card_ids
    }
    known = {(card_id, str(tag_id)) for card_id, tag_id in CardOracleTag.objects.order_by().values_list('card_id', 'tag_id')}
    added = wanted - known
    removed = known - wanted
    CardOracleTag.objects.bulk_create(
        [CardOracleTag(card_id=card_id, tag_id=tag_id) for card_id, tag_id in added],
        batch_size=DEFAULT_BATCH_SIZE,
    )
    removed_by_tag = defaultdict[str, list[int]](list)
    for card_id, tag_id in removed:
        removed_by_tag[tag_id].append(card_id)
    for tag_id, tag_card_ids in removed_by_tag.items():
        for start in range(0, len(tag_card_ids), DEFAULT_BATCH_SIZE):
            CardOracleTag.objects.filter(tag_id=UUID(tag_id), card_id__in=tag_card_ids[start:start + DEFAULT_BATCH_SIZE]).delete()
    return len(added), len(removed)
