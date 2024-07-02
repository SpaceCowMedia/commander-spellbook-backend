from typing import Any
from types import MethodType
from datetime import datetime
from django.db.models import TextField, DateTimeField, Count, Q
from django.contrib import admin
from django.db.models.query import QuerySet
from django.forms import ModelForm
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.formats import localize
from django.forms import Textarea
from django.core.exceptions import FieldDoesNotExist
from django.contrib.admin import ModelAdmin
from django.contrib.admin.views.main import ORDER_VAR, ChangeList
from adminsortable2.admin import SortableAdminBase
from django.utils.safestring import SafeText
from spellbook.variants.variants_generator import DEFAULT_CARD_LIMIT
from spellbook.models.utils import sanitize_newlines_apostrophes_and_quotes, sanitize_mana, sanitize_scryfall_query, SORTED_COLORS


def datetime_to_html(datetime: datetime | None) -> SafeText:
    if datetime is None:
        return mark_safe('-')
    return format_html('<span class="local-datetime" data-iso="{}">{}</span>', datetime.isoformat(), localize(datetime))


class NormalizedTextareaWidget(Textarea):
    def value_from_datadict(self, data, files, name: str):
        s = super().value_from_datadict(data, files, name)
        return sanitize_newlines_apostrophes_and_quotes(s)


class SpellbookAdminForm(ModelForm):
    def clean_mana_needed(self):
        if self.cleaned_data['mana_needed']:
            return sanitize_mana(self.cleaned_data['mana_needed'])
        return self.cleaned_data['mana_needed']

    def clean_scryfall_query(self):
        if self.cleaned_data['scryfall_query']:
            return sanitize_scryfall_query(self.cleaned_data['scryfall_query'])
        return self.cleaned_data['scryfall_query']


class SpellbookAdminChangelist(ChangeList):
    def get_filters(self, request):
        filters = super().get_filters(request)
        self.extra_lookup_params = filters[2]
        return filters


class SpellbookModelAdmin(SortableAdminBase, ModelAdmin):
    form = SpellbookAdminForm
    search_help_text = 'Type text to search for, using spaces to separate multiple terms.' \
        ' Use " + " instead of space to require multiple terms to be present on different related objects.' \
        ' Use " | " instead of space to require at least one of the terms to be present.' \
        ' You can\'t use " + " and " | " together.'

    formfield_overrides = {
        TextField: {'widget': NormalizedTextareaWidget},
    }

    def __init__(self, model: type, admin_site: admin.AdminSite | None) -> None:
        super().__init__(model, admin_site)
        for field in self.readonly_fields:
            if isinstance(field, str):
                try:
                    f = self.model._meta.get_field(field)
                    if isinstance(f, DateTimeField):
                        field_alias = f'{field}_local'

                        @admin.display(description=f.verbose_name, ordering=field)
                        def get_local_datetime(self, obj=None, f=field):
                            if obj is not None:
                                return datetime_to_html(getattr(obj, f))
                            return None
                        setattr(self, field_alias, MethodType(get_local_datetime, self))
                        self.readonly_fields = [field_alias if n == field else n for n in self.readonly_fields]
                        self.list_display = [field_alias if n == field else n for n in self.list_display]
                        if self.fields:
                            fields = []
                            for field_name in self.fields:
                                if field_name == field:
                                    fields.append(field_alias)
                                elif isinstance(field_name, tuple):
                                    fields.append(tuple(field_alias if n == field else n for n in field_name))
                                else:
                                    fields.append(field_name)
                            self.fields = fields
                        if self.fieldsets:
                            for _, field_options in self.fieldsets:
                                fields = []
                                for field_name in field_options['fields']:
                                    if field_name == field:
                                        fields.append(field_alias)
                                    elif isinstance(field_name, tuple):
                                        fields.append(tuple(field_alias if n == field else n for n in field_name))
                                    else:
                                        fields.append(field_name)
                                field_options['fields'] = fields
                except FieldDoesNotExist:
                    pass

    def get_search_results(self, request, queryset, search_term: str):
        result = queryset
        may_have_duplicates = False
        search_done = False
        split_by_or = search_term.replace(' + ', ' ').split(' | ')
        if len(split_by_or) > 1:
            first = True
            for sub_term in split_by_or:
                sub_term = sub_term.strip()
                if sub_term:
                    partial_result, d = super().get_search_results(request, queryset, sub_term)
                    search_done = True
                    may_have_duplicates |= d
                    if first:
                        first = False
                        result = partial_result
                    else:
                        result = result | partial_result
        else:
            split_by_and = search_term.split(' + ')
            for sub_term in split_by_and:
                sub_term = sub_term.strip()
                if sub_term:
                    result, d = super().get_search_results(request, result, sub_term)
                    search_done = True
                    may_have_duplicates |= d
        if search_done and not request.GET.get(ORDER_VAR):
            result = self.sort_search_results(request, result, search_term)
        return result, may_have_duplicates

    def sort_search_results(self, request, queryset: QuerySet, search_term: str) -> QuerySet:
        return queryset

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        self.after_save_related(request, form, formsets, change)

    def after_save_related(self, request, form, formsets, change):
        pass

    def get_changelist(self, request, **kwargs: Any) -> type[ChangeList]:
        return SpellbookAdminChangelist


class CustomFilter(admin.SimpleListFilter):
    data_type = str

    def queryset(self, request: Any, queryset: QuerySet[Any]) -> QuerySet[Any] | None:
        value = self.value()
        allowed_values = {str(lookup) for lookup, _ in self.lookup_choices}
        if value is None or value not in allowed_values:
            return queryset
        return queryset.filter(self.filter(self.data_type(value))).distinct()

    def filter(self, value: data_type) -> Q:
        raise NotImplementedError()

    def get_facet_counts(self, pk_attname, filtered_qs):
        counts = {}
        for i, choice in enumerate(self.lookup_choices):
            counts[f"{i}__c"] = Count(
                pk_attname,
                filter=self.filter(choice[0])
            )
        return counts


class IdentityFilter(CustomFilter):
    title = 'identity'
    parameter_name = 'identity'

    def lookups(self, request, model_admin):
        return [(i, i) for i in SORTED_COLORS.values()]

    def filter(self, value: str) -> Q:
        return Q(identity=value)


class CardsCountListFilter(CustomFilter):
    title = 'cards count'
    parameter_name = 'cards_count'
    one_more_than_max = DEFAULT_CARD_LIMIT + 1
    one_more_than_max_display = f'{one_more_than_max}+'

    def lookups(self, request, model_admin):
        return [(i, str(i)) for i in range(2, CardsCountListFilter.one_more_than_max)] + [(CardsCountListFilter.one_more_than_max_display, CardsCountListFilter.one_more_than_max_display)]

    def filter(self, value: str) -> Q:
        match value:
            case CardsCountListFilter.one_more_than_max_display:
                return Q(cards_count__gte=CardsCountListFilter.one_more_than_max)
            case _:
                return Q(cards_count=int(value))
