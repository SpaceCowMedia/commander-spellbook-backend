from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.utils import timezone
from spellbook.models import SaltVote, Variant, recompute_salt
from ..testing import SpellbookTestCaseWithSeeding


class SaltVoteTests(SpellbookTestCaseWithSeeding):
    variant_id: str

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        super().generate_and_publish_variants()
        cls.variant_id = Variant.objects.order_by('id').values_list('id', flat=True)[0]

    def vote(self, *scores: int, variant_id: str | None = None) -> list[SaltVote]:
        return [
            SaltVote.objects.create(user=User.objects.create(username=f'voter{User.objects.count()}'), variant_id=variant_id or self.variant_id, score=score)
            for score in scores
        ]

    def expire(self, votes: list[SaltVote]):
        SaltVote.objects.filter(pk__in=[vote.pk for vote in votes]).update(updated=timezone.now() - settings.SALT_VOTE_WINDOW - timedelta(days=1))

    def stored_salt(self, variant_id: str | None = None) -> tuple[float | None, int]:
        variant = Variant.objects.get(pk=variant_id or self.variant_id)
        return variant.salt, variant.salt_vote_count

    def test_score_ranges_from_0_to_4(self):
        for score in (0, 4):
            SaltVote(user=self.user, variant_id=self.variant_id, score=score).full_clean()
        for score in (-1, 5):
            with self.subTest(score=score), self.assertRaises(ValidationError):
                SaltVote(user=self.user, variant_id=self.variant_id, score=score).full_clean()

    def test_one_vote_per_user_and_variant(self):
        SaltVote.objects.create(user=self.user, variant_id=self.variant_id, score=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SaltVote.objects.create(user=self.user, variant_id=self.variant_id, score=2)

    def test_deleting_a_user_deletes_their_votes(self):
        [vote] = self.vote(3)
        vote.user.delete()
        self.assertFalse(SaltVote.objects.exists())

    def test_votes_outlive_their_variant(self):
        with override_settings(SALT_VOTE_MIN_COUNT=1):
            self.vote(1, 3)
            Variant.objects.filter(pk=self.variant_id).delete()
            self.assertEqual(SaltVote.objects.count(), 2)
            self.assertEqual(recompute_salt(), 0)
            self.generate_variants()
            recompute_salt()
            self.assertEqual(self.stored_salt(), (2.0, 2))

    def test_average_is_published_from_the_minimum_count(self):
        with override_settings(SALT_VOTE_MIN_COUNT=3):
            self.vote(1, 1)
            recompute_salt()
            self.assertEqual(self.stored_salt(), (None, 2))
            self.vote(2)
            recompute_salt()
            self.assertEqual(self.stored_salt(), (1.33, 3))

    def test_expired_votes_stop_counting(self):
        with override_settings(SALT_VOTE_MIN_COUNT=2):
            votes = self.vote(4, 4, 0)
            self.expire(votes[2:])
            recompute_salt()
            self.assertEqual(self.stored_salt(), (4.0, 2))
            self.expire(votes)
            recompute_salt()
            self.assertEqual(self.stored_salt(), (None, 0))

    def test_recompute_patches_the_serialized_variant(self):
        unserialized_id = Variant.objects.exclude(pk=self.variant_id).values_list('id', flat=True)[0]
        Variant.objects.filter(pk=unserialized_id).update(serialized=None)
        with override_settings(SALT_VOTE_MIN_COUNT=1):
            self.vote(2)
            self.vote(3, variant_id=unserialized_id)
            self.assertEqual(recompute_salt(), 2)
        variant = Variant.objects.defer(None).get(pk=self.variant_id)
        self.assertEqual((variant.serialized['salt'], variant.serialized['salt_vote_count']), (2.0, 1))
        self.assertIsNone(Variant.objects.defer(None).get(pk=unserialized_id).serialized)
        self.assertEqual(self.stored_salt(unserialized_id), (3.0, 1))

    def test_recompute_is_idempotent_and_leaves_variants_untouched(self):
        updated = Variant.objects.get(pk=self.variant_id).updated
        self.vote(1, 2, 3, 4, 4)
        self.assertEqual(recompute_salt(), 1)
        self.assertEqual(recompute_salt(), 0)
        self.assertEqual(self.stored_salt(), (2.8, 5))
        self.assertEqual(Variant.objects.get(pk=self.variant_id).updated, updated)
