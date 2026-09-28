from datetime import datetime
from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator
from django.db import models, router, transaction
from django.db.models import Avg, Count, FloatField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce, Round
from django.utils import timezone
from .variant import Variant
from .utils import DEFAULT_BATCH_SIZE


MAX_SALT = 4


class SaltVote(models.Model):
    id: int
    user_id: int
    variant_id: str
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='salt_votes', editable=False, db_index=False, help_text='User that cast this vote')
    variant = models.ForeignKey(Variant, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, related_name='salt_votes', editable=False, help_text='Variant this vote is about')
    score = models.PositiveSmallIntegerField(validators=[MaxValueValidator(MAX_SALT)], help_text='How salty the variant is, from 0 (not at all) to 4 (the most)')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = 'salt vote'
        verbose_name_plural = 'salt votes'
        constraints = [
            models.UniqueConstraint(fields=['user', 'variant'], name='unique_salt_vote'),
        ]
        indexes = [
            models.Index(fields=['variant', 'updated']),
        ]


def salt_window_start() -> datetime:
    return timezone.now() - settings.SALT_VOTE_WINDOW


def average_salt() -> Round:
    return Round(Avg('score', output_field=FloatField()), 2)


def live_salt_annotations(since: datetime) -> dict:
    votes = SaltVote.objects.filter(variant_id=OuterRef('variant_id'), updated__gte=since).order_by().values('variant_id')
    return {
        'average': Subquery(votes.annotate(average=average_salt()).values('average')[:1]),
        'vote_count': Coalesce(Subquery(votes.annotate(count=Count('pk')).values('count')[:1]), 0),
    }


def recompute_salt() -> int:
    counted = SaltVote.objects.filter(updated__gte=salt_window_start())
    with transaction.atomic(using=router.db_for_write(Variant)):
        truth = {
            variant_id: (average if count >= settings.SALT_VOTE_MIN_COUNT else None, count)
            for variant_id, average, count in counted
            .order_by()
            .values('variant_id')
            .annotate(average=average_salt(), count=Count('pk'))
            .values_list('variant_id', 'average', 'count')
        }
        stored = Variant.objects \
            .filter(Q(salt_vote_count__gt=0) | Q(salt__isnull=False) | Q(pk__in=counted.values('variant_id'))) \
            .order_by() \
            .values_list('pk', 'salt', 'salt_vote_count')
        drift = {pk: truth.get(pk, (None, 0)) for pk, salt, count in stored if (salt, count) != truth.get(pk, (None, 0))}
        if not drift:
            return 0
        variants = list[Variant](Variant.objects.defer(None).only('pk', 'salt', 'salt_vote_count', 'serialized').filter(pk__in=drift).order_by())
        for variant in variants:
            variant.salt, variant.salt_vote_count = drift[variant.pk]
            if variant.serialized is not None:
                variant.serialized['salt'] = variant.salt
                variant.serialized['salt_vote_count'] = variant.salt_vote_count
        Variant.objects.bulk_update(variants, fields=['salt', 'salt_vote_count', 'serialized'], skip_pre_save=True, batch_size=DEFAULT_BATCH_SIZE)
        return len(variants)
