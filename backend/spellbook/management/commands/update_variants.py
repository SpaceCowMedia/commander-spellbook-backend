from spellbook.models import Variant, batch_size_or_default
from spellbook.models.combo import Combo
from django.db.models import Subquery, OuterRef, Count, Q
from django.db.models.functions import Coalesce
from django.db import transaction
from ..abstract_command import AbstractCommand
from ..edhrec import edhrec, update_variants


class Command(AbstractCommand):
    name = 'update_variants'
    help = 'Updates variants using cards and EDHREC data'
    batch_size = batch_size_or_default(4500)

    def run(self, *args, **options):
        # Combos
        self.log('Updating combos...')
        Combo.objects.update(
            variant_count=Coalesce(
                Subquery(
                    Variant
                    .objects
                    .filter(status__in=Variant.public_statuses())
                    .filter(of=OuterRef('pk'))
                    .order_by()
                    .values('of')
                    .annotate(total=Count('pk'))
                    .values('total'),
                ),
                0,
            ),
        )
        self.log('Updating combos...done', self.style.SUCCESS)
        # Variants
        self.log('Fetching EDHREC dataset...')
        edhrec_variant_db = edhrec()
        self.log('Fetching Commander Spellbook dataset...')
        variants_query = Variant.recipes_prefetched.all()
        self.log('Updating variants...')
        updated_variant_count = 0
        variants_count = variants_query.count()
        batch_count = (variants_count + self.batch_size - 1) // self.batch_size
        for i in range(0, variants_count, self.batch_size):
            self.log(f'Starting batch {i // self.batch_size + 1}/{batch_count}...')
            with transaction.atomic(durable=True):
                variants = list[Variant](variants_query[i:i + self.batch_size])
            variants_counts: dict[str, int] = {
                i: c
                for i, c in Variant
                .objects
                .order_by()
                .filter(pk__in=(v.pk for v in variants))
                .annotate(variant_count_updated=Count(
                    'of__variants',
                    distinct=True,
                    filter=Q(of__variants__status__in=Variant.public_statuses()),
                ))
                .values_list('id', 'variant_count_updated')
            }
            variants_to_save = update_variants(
                variants,
                edhrec_variant_db,
                variants_counts,
            )
            updated_variant_count += len(variants_to_save)
            self.log(f'  Saving {len(variants_to_save)} updated variants...')
            Variant.objects.bulk_update(variants_to_save, fields=Variant.computed_fields() + ['popularity', 'variant_count'])
            del variants, variants_counts, variants_to_save
        del variants_query
        self.log(f'Updating variants...done, updated {updated_variant_count} variants', self.style.SUCCESS)
