from django.db import models
from django.core.validators import RegexValidator


FEATURED_COMBOS_TITLE_PROPERTY_TEMPLATE = 'featured_combos_title_%i'
FEATURED_SET_CODES_PROPERTY_TEMPLATE = 'featured_set_codes_%i'
FEATURED_TABS_COUNT = 3
FEATURED_COMBOS_TITLE_PROPERTIES = [FEATURED_COMBOS_TITLE_PROPERTY_TEMPLATE % i for i in range(1, FEATURED_TABS_COUNT + 1)]
FEATURED_SET_CODES_PROPERTIES = [FEATURED_SET_CODES_PROPERTY_TEMPLATE % i for i in range(1, FEATURED_TABS_COUNT + 1)]
COMBO_OF_THE_DAY_PROPERTY = 'combo_of_the_day'


PROPERTY_KEYS = [
    COMBO_OF_THE_DAY_PROPERTY,
    *FEATURED_COMBOS_TITLE_PROPERTIES,
    *FEATURED_SET_CODES_PROPERTIES,
]


class WebsiteProperty(models.Model):
    key = models.CharField(max_length=100, unique=True, blank=False, primary_key=True, editable=False)
    value = models.CharField(max_length=1000, blank=True, validators=[RegexValidator(r'^[^\,]+(?:\,[^\,]+)*$')], help_text='Comma-separated list of values')
    description = models.TextField(blank=True)

    def __str__(self):
        return self.key.replace("_", " ").title()

    class Meta:
        verbose_name = 'Website Property'
        verbose_name_plural = 'Website Properties'
        ordering = ['key']
