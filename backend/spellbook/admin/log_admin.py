from django.utils.html import format_html
from django.contrib import admin
from django.contrib.admin.models import LogEntry, DELETION
from .utils import SpellbookModelAdmin, datetime_to_html


@admin.register(LogEntry)
class LogEntryAdmin(SpellbookModelAdmin):
    date_hierarchy = 'action_time'
    list_filter = ['content_type', 'action_flag']
    search_fields = ['object_repr', 'change_message', 'user__username']
    list_display = ['action_time_local', 'user', 'content_type', 'object_link', 'action_flag']

    @admin.display(description='Action Time')
    def action_time_local(self, obj: LogEntry) -> str | None:
        return datetime_to_html(obj.action_time)

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    @admin.display(ordering='object_repr', description='object')
    def object_link(self, obj: LogEntry) -> str:
        if obj.action_flag == DELETION:
            return format_html('{}', obj.object_repr)
        if obj.get_admin_url():
            return format_html('<a href="{}">{}</a>', obj.get_admin_url(), obj.object_repr)
        return format_html('{}', obj.object_repr)
