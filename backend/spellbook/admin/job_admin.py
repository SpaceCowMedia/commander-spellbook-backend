from django.db.models import Count
from django.contrib import admin
from spellbook.models.job import Job
from .utils import SpellbookModelAdmin


@admin.register(Job)
class JobAdmin(SpellbookModelAdmin):
    date_hierarchy = 'created'
    readonly_fields = ['created', 'expected_termination', 'termination']
    fields = ['id', 'name', 'status', 'created', 'expected_termination', 'termination', 'message', 'started_by']
    list_display = ['id', 'name', 'status', 'created', 'expected_termination', 'termination', 'variants_count']
    list_filter = ['name', 'status']

    def variants_count(self, obj):
        return obj.variants_count

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(variants_count=Count('variants', distinct=True))
