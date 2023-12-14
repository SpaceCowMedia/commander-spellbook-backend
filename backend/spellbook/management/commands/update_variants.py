from spellbook.models import Variant
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
        updated_variants_count = len(variants_to_save)
        Variant.objects.bulk_update(variants_to_save, fields=Variant.playable_fields(), batch_size=5000)
        self.log('Updating variants...done', self.style.SUCCESS)
        if updated_variants_count > 0:
            self.log(f'Successfully updated {updated_variants_count} variants', self.style.SUCCESS)
        else:
            self.log('No variants to update', self.style.SUCCESS)
