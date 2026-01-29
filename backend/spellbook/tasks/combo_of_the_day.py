import logging
from django.tasks import task
from spellbook.models import Variant
from spellbook.views import VariantViewSet
from website.models import COMBO_OF_THE_DAY_PROPERTY, WebsiteProperty
from .discord_webhook import discord_webhook


logger = logging.getLogger(__name__)


@task(priority=10)
def combo_of_the_day_task():
    '''Replaces the combo of the day with a random public variant different from the current one.'''
    logger.info('Replacing the combo of the day...')
    website_property = WebsiteProperty.objects.get(key=COMBO_OF_THE_DAY_PROPERTY)
    current_combo = website_property.value.strip() or None
    if current_combo:
        try:
            variant = Variant.objects.get(pk=current_combo)
            current_combo = variant.pk
        except Variant.DoesNotExist:
            logger.error(f'Current combo of the day ({current_combo}) does not exist')
            current_combo = None
            website_property.value = ''
    new_combo = VariantViewSet().get_queryset().filter(status__in=Variant.public_statuses()).exclude(pk=current_combo).order_by('?').first()
    announcement = None
    if new_combo:
        website_property.value = str(new_combo.pk)
        logger.info(f'Combo of the day has been {'replaced with' if current_combo else 'set to'} {new_combo.pk}: {new_combo.name}')
        announcement = f'# ♾️ New Combo of the Day! ♾️\n\n[{new_combo.name}]({new_combo.spellbook_link(raw=True)})'
    website_property.save()
    if announcement:
        discord_webhook(announcement)
