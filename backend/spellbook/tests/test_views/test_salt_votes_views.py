import json
import logging
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models import QuerySet
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from common.inspection import json_to_python_lambda
from spellbook.models import SaltVote, Variant, recompute_all_counts, recompute_salt
from ..testing import SpellbookTestCaseWithSeeding


class SaltVoteViewsTests(SpellbookTestCaseWithSeeding):
    votable: QuerySet[Variant]
    variant_id: str
    other_variant_id: str
    voter: User
    permissions: QuerySet[Permission]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        super().generate_and_publish_variants()
        cls.votable = Variant.objects.filter(status__in=Variant.public_statuses(), legal_commander=True, spoiler=False)
        cls.variant_id, cls.other_variant_id = cls.votable.order_by('id').values_list('id', flat=True)[:2]
        cls.voter = User.objects.create(username='voter')
        cls.permissions = Permission.objects.filter(content_type=ContentType.objects.get_for_model(SaltVote))
        cls.voter.user_permissions.add(*cls.permissions)

    def setUp(self):
        super().setUp()
        logger = logging.getLogger('django.request')
        self.previous_level = logger.getEffectiveLevel()
        logger.setLevel(logging.ERROR)

    def tearDown(self):
        logging.getLogger('django.request').setLevel(self.previous_level)
        super().tearDown()

    def parse(self, response):
        return json.loads(response.content, object_hook=json_to_python_lambda)

    def put(self, variant_id: str, data):
        return self.client.put(reverse('salt-votes-detail', args=[variant_id]), data, content_type='application/json', follow=True)

    def delete(self, variant_id: str):
        return self.client.delete(reverse('salt-votes-detail', args=[variant_id]), follow=True)

    def retrieve(self, variant_id: str):
        return self.client.get(reverse('salt-votes-detail', args=[variant_id]), follow=True)

    def list_votes(self, **query_params):
        return self.client.get(reverse('salt-votes-list'), query_params=query_params, follow=True)

    def queue(self, **query_params):
        return self.client.get(reverse('salt-votes-queue'), query_params=query_params, follow=True)

    def queue_ids(self, **query_params) -> set[str]:
        response = self.queue(**query_params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {variant.id for variant in self.parse(response)}

    def vote_as_others(self, *scores: int, variant_id: str | None = None) -> list[SaltVote]:
        return [
            SaltVote.objects.create(user=User.objects.create(username=f'other{User.objects.count()}'), variant_id=variant_id or self.variant_id, score=score)
            for score in scores
        ]

    def expire(self, votes):
        votes.update(updated=timezone.now() - settings.SALT_VOTE_WINDOW - timedelta(days=1))

    def test_anonymous_users_can_browse_but_not_vote(self):
        response = self.list_votes()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.parse(response).results, [])
        self.assertEqual(self.retrieve(self.variant_id).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.put(self.variant_id, {'score': 2}).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.delete(self.variant_id).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertGreater(len(self.queue_ids()), 0)
        self.assertFalse(SaltVote.objects.exists())

    def test_voting_requires_both_the_add_and_change_permissions(self):
        self.client.force_login(self.user)
        self.assertEqual(self.put(self.variant_id, {'score': 2}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.delete(self.variant_id).status_code, status.HTTP_403_FORBIDDEN)
        for codename in ('add_saltvote', 'change_saltvote'):
            with self.subTest(codename=codename):
                self.user.user_permissions.set(self.permissions.filter(codename=codename))
                self.assertEqual(self.put(self.variant_id, {'score': 2}).status_code, status.HTTP_403_FORBIDDEN)
        self.user.user_permissions.set(self.permissions.filter(codename__in=('add_saltvote', 'change_saltvote')))
        self.assertEqual(self.put(self.variant_id, {'score': 2}).status_code, status.HTTP_201_CREATED)

    def test_casting_and_changing_a_vote(self):
        self.client.force_login(self.voter)
        response = self.put(self.variant_id, {'score': 3})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result = self.parse(response)
        self.assertEqual((result.variant, result.score, result.average, result.vote_count), (self.variant_id, 3, 3.0, 1))
        yesterday = timezone.now() - timedelta(days=1)
        SaltVote.objects.update(updated=yesterday)
        response = self.put(self.variant_id, {'score': 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        changed = self.parse(response)
        self.assertEqual((changed.score, changed.average, changed.vote_count, changed.created), (1, 1.0, 1, result.created))
        vote = SaltVote.objects.get()
        self.assertEqual(vote.score, 1)
        self.assertGreater(vote.updated, yesterday)
        self.assertEqual(self.parse(self.retrieve(self.variant_id)), changed)

    def test_invalid_scores_are_rejected(self):
        self.client.force_login(self.voter)
        for data in ({'score': 5}, {'score': -1}, {'score': 'a'}, {'score': 2.5}, {'score': None}, {}):
            with self.subTest(data=data):
                self.assertEqual(self.put(self.variant_id, data).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(SaltVote.objects.exists())

    def test_only_public_variants_can_be_voted(self):
        self.client.force_login(self.voter)
        self.assertEqual(self.put('missing', {'score': 2}).status_code, status.HTTP_404_NOT_FOUND)
        for variant_status in (Variant.Status.NEW, Variant.Status.DRAFT, Variant.Status.REFERENCE, Variant.Status.EXAMPLE):
            with self.subTest(status=variant_status):
                Variant.objects.filter(pk=self.variant_id).update(status=variant_status)
                expected = status.HTTP_201_CREATED if variant_status in Variant.public_statuses() else status.HTTP_404_NOT_FOUND
                self.assertEqual(self.put(self.variant_id, {'score': 2}).status_code, expected)
        recompute_all_counts()

    def test_the_live_average_counts_every_recent_vote(self):
        self.expire(SaltVote.objects.filter(pk__in=[vote.pk for vote in self.vote_as_others(4, 2, 0)][2:]))
        self.client.force_login(self.voter)
        result = self.parse(self.put(self.variant_id, {'score': 3}))
        self.assertEqual((result.average, result.vote_count), (3.0, 3))
        self.assertEqual(self.parse(self.list_votes()).results[0].average, 3.0)
        variant = Variant.objects.get(pk=self.variant_id)
        self.assertEqual((variant.salt, variant.salt_vote_count), (None, 0))

    def test_votes_are_private(self):
        [vote] = self.vote_as_others(2)
        self.client.force_login(self.voter)
        self.assertEqual(self.parse(self.list_votes()).results, [])
        self.assertEqual(self.retrieve(self.variant_id).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.delete(self.variant_id).status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(SaltVote.objects.filter(pk=vote.pk).exists())

    def test_retracting_a_vote(self):
        self.client.force_login(self.voter)
        self.put(self.variant_id, {'score': 4})
        self.assertEqual(self.delete(self.variant_id).status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.delete(self.variant_id).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.retrieve(self.variant_id).status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(SaltVote.objects.exists())

    def test_listing_votes(self):
        self.client.force_login(self.voter)
        newest_first = [self.other_variant_id, self.variant_id, 'deleted-variant']
        for age, (variant_id, score) in enumerate(zip(newest_first, (2, 1, 0))):
            SaltVote.objects.create(user=self.voter, variant_id=variant_id, score=score)
            SaltVote.objects.filter(variant_id=variant_id).update(updated=timezone.now() - timedelta(days=age))
        self.assertEqual([vote.variant for vote in self.parse(self.list_votes()).results], newest_first)
        self.assertEqual([vote.score for vote in self.parse(self.list_votes(variant=self.variant_id)).results], [1])
        self.assertEqual(self.delete('deleted-variant').status_code, status.HTTP_204_NO_CONTENT)

    def test_queue_serves_votable_variants(self):
        expected = set(self.votable.values_list('id', flat=True))
        self.assertLess(len(expected), Variant.objects.count())
        self.assertSetEqual(self.queue_ids(limit=50), expected)
        for variant in self.parse(self.queue(limit=50)):
            with self.subTest(variant=variant.id):
                self.assertEqual(variant, self.parse(self.client.get(reverse('variants-detail', args=[variant.id]), follow=True)))

    def test_queue_leaves_out_recent_votes(self):
        self.client.force_login(self.voter)
        self.put(self.variant_id, {'score': 1})
        self.assertNotIn(self.variant_id, self.queue_ids(limit=50))
        self.expire(SaltVote.objects.all())
        self.assertIn(self.variant_id, self.queue_ids(limit=50))

    def test_queue_limit(self):
        self.assertLessEqual(len(self.queue_ids()), 10)
        self.assertEqual(len(self.queue_ids(limit=1)), 1)
        for limit in (0, 51, 'x'):
            with self.subTest(limit=limit):
                self.assertEqual(self.queue(limit=limit).status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(SALT_VOTE_QUEUE_POPULARITY_EXPONENT=8, SALT_VOTE_TARGET_COUNT=1)
    def test_queue_favors_popular_variants_until_they_have_enough_votes(self):
        Variant.objects.filter(pk=self.variant_id).update(popularity=10**6)
        self.assertEqual(self.queue_ids(limit=1), {self.variant_id})
        self.vote_as_others(4)
        recompute_salt()
        Variant.objects.filter(pk=self.other_variant_id).update(popularity=10**3)
        self.assertEqual(self.queue_ids(limit=1), {self.other_variant_id})

    @override_settings(SALT_VOTE_QUEUE_POPULARITY_EXPONENT=0.25)
    def test_queue_draws_unpopular_variants_less_often(self):
        Variant.objects.filter(pk=self.variant_id).update(popularity=10**4)
        Variant.objects.exclude(pk=self.variant_id).update(popularity=0)
        draws = 0
        for _ in range(200):
            draws += self.variant_id in self.queue_ids(limit=1)
        self.assertGreater(draws, 0)
        self.assertLess(draws, 120)
