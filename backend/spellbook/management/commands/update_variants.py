from spellbook.models import Variant
from spellbook.models.combo import Combo
from django.db.models import Q, Subquery, OuterRef, Count
from django.db.models.functions import Coalesce
from django.db import transaction, connection
from ..abstract_command import AbstractCommand
from ..edhrec import edhrec, update_variants


class Command(AbstractCommand):
    name = 'update_variants'
    help = 'Updates variants using cards and EDHREC data'
    batch_size = 5000 if not connection.vendor == 'sqlite' else 1000

    def run(self, *args, **options):
        self.log('Fetching EDHREC dataset...')
        edhrec_variant_db = edhrec()
        self.log('Fetching Commander Spellbook dataset...')
        variants_query = Variant.recipes_prefetched.prefetch_related('uses', 'requires', 'produces')
        self.log('Fetching variant counts...')
        updated_variant_count = 0
        variants_counts: dict[str, int] = {
            i: c
            for i, c in Variant
            .objects
            .order_by('pk')
            .annotate(variant_count_updated=Count('of__variants', distinct=True, filter=Q(of__variants__status__in=Variant.public_statuses())))
            .values_list('id', 'variant_count_updated')
        }
        self.log('Updating variants...')
        for i in range(0, variants_query.count(), self.batch_size):
            with transaction.atomic(durable=True):
                variants = list[Variant](variants_query[i:i + self.batch_size])
                variants_to_save = update_variants(
                    variants,
                    variants_counts,
                    edhrec_variant_db,
                    log=lambda x: self.log(x),
                    log_warning=lambda x: self.log(x, self.style.WARNING),
                    log_error=lambda x: self.log(x, self.style.ERROR),
                )
                updated_variant_count += len(variants_to_save)
                Variant.objects.bulk_update(variants_to_save, fields=Variant.computed_fields() + ['popularity', 'variant_count'])
                del variants, variants_counts, variants_to_save
                self.log(f'  Processed {min(i + self.batch_size, variants_query.count())} / {variants_query.count()} variants')
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
