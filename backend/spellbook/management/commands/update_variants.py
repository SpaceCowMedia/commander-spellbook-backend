from spellbook.models import Variant
from spellbook.models.combo import Combo
from django.db.models import Subquery, OuterRef, Count
from django.db.models.functions import Coalesce
from ..abstract_command import AbstractCommand
from ..edhrec import edhrec, update_variants


class Command(AbstractCommand):
    name = 'update_variants'
    help = 'Updates variants using cards and EDHREC data'

    def run(self, *args, **options):
        self.log('Fetching EDHREC dataset...')
        edhrec_variant_db = edhrec()
        self.log('Updating variants...')
        variants_query = Variant.objects.prefetch_related('uses', 'cardinvariant_set', 'templateinvariant_set')
        variants = list(variants_query)
        variants_to_save = update_variants(
            variants,
            edhrec_variant_db,
            log=lambda x: self.log(x),
            log_warning=lambda x: self.log(x, self.style.WARNING),
            log_error=lambda x: self.log(x, self.style.ERROR),
        )
        updated_variant_count = len(variants_to_save)
        Variant.objects.bulk_update(variants_to_save, fields=Variant.playable_fields() + ['popularity'], batch_size=5000)
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
