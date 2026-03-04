from django.contrib import admin
from django.http import HttpRequest
from django_tasks.backends.database.admin import DBTaskResultAdmin
from django_tasks.backends.database.models import DBTaskResult

admin.site.unregister(DBTaskResult)


class TaskNameFilter(admin.SimpleListFilter):
    title = "task name"
    parameter_name = "task_path"

    def lookups(self, request, model_admin):
        task_names: list[str] = sorted(DBTaskResult.objects.values_list("task_path", flat=True).distinct())
        return [(name, name.rsplit(".", 1)[1]) for name in task_names]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(task_path=value)
        return queryset


@admin.register(DBTaskResult)
class TaskResultAdmin(DBTaskResultAdmin):
    date_hierarchy = 'enqueued_at'
    list_filter = ('status', TaskNameFilter)
    list_display = (
        'task_name',
        'status',
        'progress',
        'id',
        'enqueued_at',
        'started_at',
        'finished_at',
        'priority',
        'queue_name',
    )

    def progress(self, obj: DBTaskResult) -> str:
        if not obj.metadata.get('progress'):
            return self.get_empty_value_display()
        return obj.metadata['progress']

    def get_fields(self, request: HttpRequest, obj: DBTaskResult | None = None):
        fields = super().get_fields(request, obj)
        fields.remove('run_after')
        return fields
