from django.contrib import admin
from .models import Card, Feature, Combo, Variant

class FeatureInline(admin.TabularInline):
    model = Card.features.through
    extra = 2

class CardAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Scryfall', {'fields': ['oracle_id']}),
        ('Spellbook', {'fields': ['name']})
    ]
    inlines = [FeatureInline]

class CardInline(admin.TabularInline):
    model = Feature.cards.through
    extra = 1

class FeatureAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {'fields': ['name', 'description']}),
    ]
    inlines = [CardInline]

class ReadOnlyAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class VariantAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    pass







admin.site.register(Card, CardAdmin)
admin.site.register(Feature, FeatureAdmin)
admin.site.register(Combo)
admin.site.register(Variant, VariantAdmin)

