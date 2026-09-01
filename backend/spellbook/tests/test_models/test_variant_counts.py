from django.contrib.messages.storage.base import BaseStorage
from django.db.models import Count
from django.test import RequestFactory
from spellbook.admin.variant_admin import set_status
from spellbook.models import Card, Combo, Variant, recompute_all_counts
from ..testing import SpellbookTestCaseWithSeeding


class SilentMessages(BaseStorage):
    def _get(self, *args, **kwargs):
        return [], True

    def _store(self, messages, response, *args, **kwargs):
        return []


class VariantCountsTests(SpellbookTestCaseWithSeeding):
    '''Covers the write paths that move a count, so that they are exercised and not only asserted.

    Every test also goes through assertVariantCountsAreExact in tearDown, which is what actually
    checks the numbers: what these add is that the paths run at all.
    '''

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        super().generate_variants()
        recompute_all_counts()

    def request(self):
        request = RequestFactory().get('/')
        request._messages = SilentMessages(request)  # type: ignore[attr-defined]
        return request

    def test_generation_leaves_nothing_to_repair(self):
        self.assertEqual(recompute_all_counts(), 0)

    def test_publishing_moves_the_counts_of_the_siblings(self):
        combo = Combo.objects.annotate(generated=Count('variants')).filter(generated__gt=1).first()
        assert combo is not None
        variant = combo.variants.first()
        assert variant is not None
        siblings = Variant.objects.filter(of__variants=variant.pk).distinct()
        self.assertGreater(siblings.count(), 1)
        self.assertEqual(variant.variant_count, 0)
        set_status(self.request(), Variant.objects.filter(pk=variant.pk), Variant.Status.OK)
        # The published variant counts itself, and so does every variant sharing a generator combo
        for sibling in siblings:
            self.assertEqual(sibling.variant_count, 1)
        for combo in Combo.objects.filter(variants=variant.pk):
            self.assertEqual(combo.public_variant_count, 1)
        for card in Card.objects.filter(used_in_variants=variant.pk):
            self.assertEqual(card.variant_count, 1)
        self.assertEqual(recompute_all_counts(), 0)

    def test_unpublishing_moves_them_back(self):
        variants = Variant.objects.all()
        set_status(self.request(), variants, Variant.Status.OK)
        self.assertFalse(Variant.objects.filter(variant_count=0).exists())
        set_status(self.request(), variants, Variant.Status.NOT_WORKING)
        self.assertFalse(Variant.objects.exclude(variant_count=0).exists())
        self.assertFalse(Combo.objects.exclude(public_variant_count=0).exists())
        self.assertFalse(Card.objects.exclude(variant_count=0).exists())
        self.assertEqual(recompute_all_counts(), 0)

    def test_a_single_save_that_crosses_the_public_boundary_is_enough(self):
        variant = Variant.objects.exclude(of=None).first()
        assert variant is not None
        variant.status = Variant.Status.EXAMPLE
        variant.save()
        self.assertEqual(Variant.objects.get(pk=variant.pk).variant_count, 1)
        self.assertEqual(recompute_all_counts(), 0)

    def test_deleting_a_combo_with_public_variants(self):
        set_status(self.request(), Variant.objects.all(), Variant.Status.OK)
        combo = Combo.objects.filter(variants__isnull=False).distinct().first()
        assert combo is not None
        combo.delete()
        # Its sole variants went to RESTORE, and the shared generator combos lost them from theirs
        self.assertEqual(recompute_all_counts(), 0)

    def test_deleting_variants_leaves_the_counts_of_the_survivors_exact(self):
        set_status(self.request(), Variant.objects.all(), Variant.Status.OK)
        Variant.objects.filter(pk__in=Variant.objects.values_list('pk', flat=True)[:2]).delete()
        # A raw delete reports nothing, which is what the periodic rebuild is there to catch
        recompute_all_counts()
        self.assertEqual(recompute_all_counts(), 0)
