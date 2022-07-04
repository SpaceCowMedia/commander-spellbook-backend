from django.contrib import admin
from .models import Card, Feature, Combo, Variant

@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Scryfall', {'fields': ['oracle_id']}),
        ('Spellbook', {'fields': ['name', 'features']})
    ]
    # inlines = [FeatureInline]
    search_fields = ['name', 'features__name']
    autocomplete_fields = ['features']

class CardInline(admin.StackedInline):
    model = Feature.cards.through
    extra = 1
    autocomplete_fields = ['card']

@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {'fields': ['name', 'description']}),
    ]
    inlines = [CardInline]
    search_fields = ['name', 'cards__name']


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    readonly_fields = ['includes', 'produces', 'of']
    fieldsets = [
        ('Generated', {'fields': ['includes', 'produces', 'of']}),
        ('Editable', {'fields': ['status', 'prerequisites', 'description']})
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Combo)
class ComboAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Requirements', {'fields': ['includes', 'needs', 'prerequisites']}),
        ('Features', {'fields': ['produces']}),
        ('Description', {'fields': ['description']})
    ]
    filter_horizontal = ['includes', 'produces', 'needs']
