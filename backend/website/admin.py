from django.contrib import admin
from .models import WebsiteProperty


@admin.register(WebsiteProperty)
class WebsitePropertyAdmin(admin.ModelAdmin):
    list_display = ('key', 'value')

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
