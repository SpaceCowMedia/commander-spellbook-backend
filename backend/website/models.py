from django.db import models
from django.core.validators import RegexValidator


FEATURED_COMBOS_TITLE = 'featured_combos_title'
FEATURED_SET_CODES = 'featured_set_codes'
COMBO_OF_THE_DAY = 'combo_of_the_day'


PROPERTY_KEYS = [
    FEATURED_COMBOS_TITLE,
    FEATURED_SET_CODES,
    COMBO_OF_THE_DAY,
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
