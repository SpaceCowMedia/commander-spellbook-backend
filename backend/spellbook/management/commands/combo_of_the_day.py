from spellbook.models import Variant
from spellbook.views import VariantViewSet
from website.models import COMBO_OF_THE_DAY, WebsiteProperty
from ..abstract_command import AbstractCommand


class Command(AbstractCommand):
    name = 'combo_of_the_day'
    help = 'Replaces the combo of the day'

    def run(self, *args, **options):
        self.log('Replacing the combo of the day...')
        website_property = WebsiteProperty.objects.get(key=COMBO_OF_THE_DAY)
        current_combo = website_property.value.strip()
        if current_combo:
            try:
                variant = Variant.objects.get(pk=current_combo)
                current_combo = variant.pk
            except Variant.DoesNotExist:
                self.log(f'Current combo of the day ({current_combo}) does not exist')
                current_combo = ''
        new_combo = VariantViewSet().get_queryset().exclude(pk=current_combo).order_by('?').first()
        if new_combo:
            website_property.value = str(new_combo.pk)
            self.log(f'Combo of the day has been replaced with {new_combo.pk}: {new_combo.name}')
            announcement = f'# ♾️ 🎉 New Combo of the Day! 🎉 ♾️\n\n' \
                           f'[{new_combo.name}]({new_combo.spellbook_link(raw=True)})'
            self.discord_webhook(announcement)
        website_property.save()
