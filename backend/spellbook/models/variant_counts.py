from django.db import transaction
from django.db.models import Count, F, IntegerField, Q, QuerySet
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver
from .card import Card
from .combo import Combo
from .utils import DEFAULT_BATCH_SIZE
from .variant import CardInVariant, Variant, VariantOfCombo


def recompute_combo_counts(combos: QuerySet[Combo]) -> int:
    '''Rewrites the two per-combo counters, returning how many rows were actually wrong.

    Combo.variant_count counts every variant whatever its status, as an editing aid telling how much
    a combo expands into. Combo.public_variant_count counts only the public ones, and is what almost
    every Variant.variant_count is derived from.
    '''
    truth = {
        combo_id: (total, public)
        for combo_id, total, public in VariantOfCombo
        .objects
        .filter(combo__in=combos.values('pk'))
        .order_by()
        .values('combo_id')
        .annotate(
            total=Count('variant_id', distinct=True),
            public=Count('variant_id', distinct=True, filter=Q(variant__status__in=Variant.public_statuses())),
        )
        .values_list('combo_id', 'total', 'public')
    }
    drifted = list[Combo]()
    for combo in combos.only('pk', 'variant_count', 'public_variant_count').order_by():
        total, public = truth.get(combo.pk, (0, 0))
        if combo.variant_count != total or combo.public_variant_count != public:
            combo.variant_count = total
            combo.public_variant_count = public
            drifted.append(combo)
    Combo.objects.bulk_update(drifted, fields=['variant_count', 'public_variant_count'], batch_size=DEFAULT_BATCH_SIZE)
    return len(drifted)


def variant_count_drift(variants: QuerySet[Variant]) -> dict[str, int]:
    '''The correct Variant.variant_count, for the given variants that do not already store it.

    A variant with a single generator combo, which is 99% of them, just inherits that combo's public
    count through a plain index lookup. Only the handful with two or more, and the orphans left
    without any, need the join counting the distinct public variants the shared combos reach.
    '''
    variant_ids = variants.values('pk')
    single = VariantOfCombo \
        .objects \
        .filter(variant__in=variant_ids) \
        .order_by() \
        .values('variant_id') \
        .annotate(of_count=Count('combo_id')) \
        .filter(of_count=1) \
        .values('variant_id')
    drifted = {
        variant_id: public_count
        for variant_id, public_count in VariantOfCombo
        .objects
        .filter(variant_id__in=single)
        .exclude(variant__variant_count=F('combo__public_variant_count'))
        .values_list('variant_id', 'combo__public_variant_count')
    }
    drifted.update(
        Variant
        .objects
        .filter(pk__in=variant_ids)
        .exclude(pk__in=single)
        .order_by()
        .annotate(truth=Count('of__variants', distinct=True, filter=Q(of__variants__status__in=Variant.public_statuses())))
        .exclude(variant_count=F('truth'))
        .values_list('pk', 'truth')
    )
    return drifted


def serialized_count_drift(variants: QuerySet[Variant]) -> set[str]:
    '''The variants whose preserialized payload disagrees with their stored column.

    The missing key has to be asked for separately: a payload written before the count joined the
    serializer has no such key at all, and comparing NULL to the column matches nothing.
    '''
    return set(
        Variant
        .objects
        .filter(pk__in=variants.values('pk'), serialized__isnull=False)
        .order_by()
        .annotate(serialized_count=Cast(KeyTextTransform('variant_count', 'serialized'), IntegerField()))
        .filter(Q(serialized_count__isnull=True) | ~Q(serialized_count=F('variant_count')))
        .values_list('pk', flat=True)
    )


def recompute_variant_counts(variants: QuerySet[Variant]) -> int:
    drift = variant_count_drift(variants)
    targets = set(drift) | serialized_count_drift(variants)
    if not targets:
        return 0
    # defer(None) clears the manager's defer('serialized'): a bare defer() is a silent no-op, and
    # would leave every blob to be refetched one row at a time
    drifted = list[Variant](Variant.objects.defer(None).filter(pk__in=targets).order_by())
    for variant in drifted:
        variant.variant_count = drift.get(variant.pk, variant.variant_count)
        if variant.serialized is not None:
            variant.serialized['variant_count'] = variant.variant_count
    Variant.objects.bulk_update(drifted, fields=['variant_count', 'serialized'], skip_pre_save=True, batch_size=DEFAULT_BATCH_SIZE)
    return len(drifted)


def recompute_card_counts(cards: QuerySet[Card]) -> int:
    truth = dict(
        Card
        .objects
        .filter(pk__in=cards.values('pk'))
        .order_by()
        .annotate(updated_variant_count=Count('used_in_variants', distinct=True, filter=Q(used_in_variants__status__in=Variant.public_statuses())))
        .exclude(variant_count=F('updated_variant_count'))
        .values_list('pk', 'updated_variant_count')
    )
    if not truth:
        return 0
    drifted = list[Card](Card.objects.filter(pk__in=truth).only('pk', 'variant_count').order_by())
    for card in drifted:
        card.variant_count = truth[card.pk]
    Card.objects.bulk_update(drifted, fields=['variant_count'], skip_pre_save=True, batch_size=DEFAULT_BATCH_SIZE)
    return len(drifted)


def recompute_all_counts() -> int:
    '''Rebuilds every counter from scratch, cheaply enough to be the safety net rather than the mechanism.'''
    with transaction.atomic():
        # The combos go first: the variant counts read back the public counts this writes
        drifted = recompute_combo_counts(Combo.objects.all())
        drifted += recompute_variant_counts(Variant.objects.all())
        drifted += recompute_card_counts(Card.objects.all())
        return drifted


def recompute_counts(*, combo_ids=(), variant_ids=()) -> int:
    '''Rebuilds the counters that the given combos and variants can have invalidated.

    The affected set is closed over the sibling relation: a variant's count depends on the statuses
    of the variants sharing a generator combo with it, so touching any combo invalidates every
    variant of that combo. Over-approximating the set is always safe, because the recompute is
    absolute rather than a delta, and so is idempotent and self-healing.
    '''
    combos = set(combo_ids)
    if variant_ids:
        combos.update(VariantOfCombo.objects.filter(variant_id__in=variant_ids).values_list('combo_id', flat=True))
    variants = set(variant_ids)
    if combos:
        variants.update(VariantOfCombo.objects.filter(combo_id__in=combos).values_list('variant_id', flat=True))
    if not combos and not variants:
        return 0
    cards = CardInVariant.objects.filter(variant_id__in=variants).values('card_id')
    with transaction.atomic():
        # The combos go first: the variant counts read back the public counts this writes
        drifted = recompute_combo_counts(Combo.objects.filter(pk__in=combos))
        drifted += recompute_variant_counts(Variant.objects.filter(pk__in=variants))
        drifted += recompute_card_counts(Card.objects.filter(pk__in=cards))
        return drifted


@receiver(post_save, sender=Variant, dispatch_uid='variant_saved_counts')
def variant_saved_counts(sender, instance: Variant, created: bool, raw=False, **kwargs):
    # The bulk paths skip signals, and the ones that change a status recount on their own. This
    # covers every remaining single row save, whoever makes it.
    if raw:
        return
    status = instance.__dict__.get('status')
    if status is None:
        return
    public_statuses = Variant.public_statuses()
    if created or (instance._status in public_statuses) != (status in public_statuses):
        recompute_counts(variant_ids=[instance.pk])
    instance._status = status


# Deleting a combo both sends its sole variants to RESTORE and cascades the VariantOfCombo rows
# away, so the variants to recount have to be read before the delete and used after it
variants_of_deleted_combos: dict[int, set[str]] = {}


@receiver(pre_delete, sender=Combo, dispatch_uid='combo_deleted_counts')
def combo_delete_counts(sender, instance: Combo, **kwargs):
    variants_of_deleted_combos[instance.pk] = set(VariantOfCombo.objects.filter(combo=instance).values_list('variant_id', flat=True))


@receiver(post_delete, sender=Combo, dispatch_uid='combo_deleted_counts_applied')
def combo_deleted_counts(sender, instance: Combo, **kwargs):
    variant_ids = variants_of_deleted_combos.pop(instance.pk, None)
    if variant_ids:
        recompute_counts(variant_ids=variant_ids)
