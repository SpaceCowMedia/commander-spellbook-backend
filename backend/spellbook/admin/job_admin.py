from django.contrib import admin
from ..models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    fields = ['id', 'name', 'status', 'created', 'expected_termination', 'termination', 'message', 'started_by']
    list_display = ['id', 'name', 'status', 'created', 'expected_termination', 'termination', 'variants_count']

    def variants_count(self, obj):
        return obj.variants.count()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
