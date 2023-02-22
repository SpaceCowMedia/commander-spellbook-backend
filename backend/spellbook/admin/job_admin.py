from django.contrib import admin
from django.utils.html import format_html
from django.utils.formats import localize
from ..models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    readonly_fields = ['created_local', 'expected_termination_local', 'termination_local']
    fields = ['id', 'name', 'status', 'created_local', 'expected_termination_local', 'termination_local', 'message', 'started_by']
    list_display = ['id', 'name', 'status', 'created', 'expected_termination', 'termination', 'variants_count']

    def variants_count(self, obj):
        return obj.variants.count()

    def datetime_to_html(self, datetime):
        return format_html('<span class="local-datetime" title="{}">{}</span>', datetime.isoformat(), localize(datetime))

    @admin.display(description='Created')
    def created_local(self, obj):
        return self.datetime_to_html(obj.created)

    @admin.display(description='Expected Termination')
    def expected_termination_local(self, obj):
        return self.datetime_to_html(obj.expected_termination)

    @admin.display(description='Termination')
    def termination_local(self, obj):
        return self.datetime_to_html(obj.termination)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
