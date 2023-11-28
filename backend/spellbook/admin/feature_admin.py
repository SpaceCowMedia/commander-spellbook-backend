from django.contrib import admin
from django.forms import ModelForm
from spellbook.models import Feature
from .utils import NormalizedTextField


class CardInFeatureAdminInline(admin.StackedInline):
    model = Feature.cards.through
    extra = 1
    autocomplete_fields = ['card']
    verbose_name = 'Produced by card'
    verbose_name_plural = 'Produced by cards'


class FeatureAdminForm(ModelForm):
    class Meta:
        field_classes = {
            'description': NormalizedTextField,
        }


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    form = FeatureAdminForm
    fieldsets = [
        (None, {'fields': ['name', 'utility', 'description']}),
    ]
    inlines = [CardInFeatureAdminInline]
    search_fields = ['name', 'cards__name']
    list_display = ['name', 'id', 'utility']
    list_filter = ['utility']
