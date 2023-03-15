from django.contrib import admin
from django.utils.html import format_html
from django.utils.formats import localize
from ..models import Job
from django.db.models import Count
from .utils import datetime_to_html


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    readonly_fields = ['created_local', 'expected_termination_local', 'termination_local']
    fields = ['id', 'name', 'status', 'created_local', 'expected_termination_local', 'termination_local', 'message', 'started_by']
    list_display = ['id', 'name', 'status', 'created_local', 'expected_termination_local', 'termination_local', 'variants_count']

    def variants_count(self, obj):
        return obj.variants_count

    @admin.display(description='Created')
    def created_local(self, obj):
        return datetime_to_html(obj.created)

    @admin.display(description='Expected Termination')
    def expected_termination_local(self, obj):
        return datetime_to_html(obj.expected_termination)

    @admin.display(description='Termination')
    def termination_local(self, obj):
        return datetime_to_html(obj.termination)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(variants_count=Count('variants'))
