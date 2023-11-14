from django.db import models
from django.core.validators import RegexValidator


FEATURED_SET_CODES = 'featured_set_codes'


PROPERTY_KEYS = [
    'featured_combos_title',
    FEATURED_SET_CODES,
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
