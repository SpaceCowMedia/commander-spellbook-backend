from spellbook.models import Variant
from spellbook.models.combo import Combo
from django.db.models import Subquery, OuterRef, Count
from django.db.models.functions import Coalesce
from django.db import transaction, connection
from ..abstract_command import AbstractCommand
from ..edhrec import edhrec, update_variants


class Command(AbstractCommand):
    name = 'update_variants'
    help = 'Updates variants using cards and EDHREC data'
    batch_size = 5000 if not connection.vendor == 'sqlite' else 1000

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
        variants_query = Variant.recipes_prefetched.prefetch_related('uses', 'requires', 'produces')
        self.log('Updating variants...')
        updated_variant_count = 0
        for i in range(0, variants_query.count(), self.batch_size):
            self.log(f'Starting batch {i // self.batch_size + 1}...')
            with transaction.atomic(durable=True):
                variants = list[Variant](variants_query[i:i + self.batch_size])
            Variant.objects.filter(pk__in=variants).update(
                variant_count=Coalesce(
                    Subquery(
                        Variant
                        .objects
                        .filter(status__in=Variant.public_statuses())
                        .filter(of__variants=OuterRef('pk'))
                        .order_by()
                        .distinct()
                        .values('of__variants')
                        .annotate(total=Count('pk'))
                        .values('total'),
                    ),
                    0,
                ),
            )
            variants_to_save = update_variants(
                variants,
                edhrec_variant_db,
                log=lambda x: self.log(x),
                log_warning=lambda x: self.log(x, self.style.WARNING),
                log_error=lambda x: self.log(x, self.style.ERROR),
            )
            updated_variant_count += len(variants_to_save)
            Variant.objects.bulk_update(variants_to_save, fields=Variant.computed_fields() + ['popularity'])
            del variants, variants_to_save
            self.log(f'  Processed {min(i + self.batch_size, variants_query.count())} / {variants_query.count()} variants')
        del variants_query
        self.log(f'Updating variants...done, updated {updated_variant_count} variants', self.style.SUCCESS)
