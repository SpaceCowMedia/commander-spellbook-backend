from spellbook.models import Variant
from spellbook.models.combo import Combo
from django.db.models import Q, Subquery, OuterRef, Count
from django.db.models.functions import Coalesce
from ..abstract_command import AbstractCommand
from ..edhrec import edhrec, update_variants


class Command(AbstractCommand):
    name = 'update_variants'
    help = 'Updates variants using cards and EDHREC data'
    batch_size = 5000

    def run(self, *args, **options):
        self.log('Fetching EDHREC dataset...')
        edhrec_variant_db = edhrec()
        self.log('Updating variants...')
        variants_query = Variant.objects.prefetch_related('uses', 'cardinvariant_set', 'templateinvariant_set')
        variants = list[Variant]()
        for i in range(0, variants_query.count(), self.batch_size):
            variants.extend(variants_query[i:i + self.batch_size])
        variants_counts: dict[str, int] = {
            i: c
            for i, c in Variant
            .objects
            .order_by('pk')
            .annotate(variant_count_updated=Count('of__variants', distinct=True, filter=Q(of__variants__status__in=Variant.public_statuses())))
            .values_list('id', 'variant_count_updated')
        }
        variants_to_save = update_variants(
            variants,
            variants_counts,
            edhrec_variant_db,
            log=lambda x: self.log(x),
            log_warning=lambda x: self.log(x, self.style.WARNING),
            log_error=lambda x: self.log(x, self.style.ERROR),
        )
        updated_variant_count = len(variants_to_save)
        Variant.objects.bulk_update(variants_to_save, fields=Variant.playable_fields() + ['popularity', 'variant_count'], batch_size=self.batch_size)
        self.log('Updating variants...done', self.style.SUCCESS)
        if updated_variant_count > 0:
            self.log(f'Successfully updated {updated_variant_count} variants', self.style.SUCCESS)
        else:
            self.log('No variants to update', self.style.SUCCESS)
        # Combos
        self.log('Updating combos...')
        Combo.objects.update(
            variant_count=Coalesce(
                Subquery(
                    Variant
                    .objects
                    .filter(status__in=Variant.public_statuses())
                    .filter(of=OuterRef('pk'))
                    .values('of')
                    .annotate(total=Count('pk'))
                    .values('total'),
                ),
                0,
            ),
        )
        self.log('Updating combos...done', self.style.SUCCESS)
