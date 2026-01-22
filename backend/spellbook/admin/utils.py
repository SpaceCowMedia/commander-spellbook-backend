from typing import Any
from types import MethodType
from datetime import datetime
from django.db.models import TextField, DateTimeField, Count, Q, When, Case, Max
from django.contrib import admin
from django.db.models.query import QuerySet
from django.http import HttpRequest
from django.forms import ModelForm
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.formats import localize
from django.forms import Textarea
from django.core.exceptions import FieldDoesNotExist
from django.contrib.admin import ModelAdmin
from django.contrib.admin.views.main import ORDER_VAR, ChangeList
from django.utils.safestring import SafeText
from constants import SORTED_COLORS
from adminsortable2.admin import SortableAdminBase
from spellbook.variants.variants_generator import DEFAULT_CARD_LIMIT
from spellbook.models.utils import sanitize_newlines_apostrophes_and_quotes, sanitize_mana, sanitize_scryfall_query


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
        ' Wrap terms in quotes to search for exact phrases.' \
        ' Use " + " instead of space to require multiple terms to be present on different related objects.' \
        ' Use " | " instead of space to require at least one of the terms to be present.' \
        ' You can\'t use " + " and " | " together.'

    formfield_overrides = {
        TextField: {'widget': NormalizedTextareaWidget},
    }

    def __init__(self, model: type, admin_site: admin.AdminSite | None):
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
        search_done = False
        split_by_or = search_term.replace(' + ', ' ').split(' | ')
        sub_terms: list[str] = []
        if len(split_by_or) > 1:
            may_have_duplicates = False
            first = True
            for sub_term in split_by_or:
                sub_term = sub_term.strip()
                if sub_term:
                    sub_terms.append(sub_term)
                    partial_result, d = super().get_search_results(request, queryset, sub_term)
                    search_done = True
                    may_have_duplicates |= d
                    if first:
                        first = False
                        result = partial_result
                    else:
                        result = result | partial_result
        else:
            may_have_duplicates = True
            split_by_and = search_term.split(' + ')
            for sub_term in split_by_and:
                sub_term = sub_term.strip()
                if sub_term:
                    sub_terms.append(sub_term)
                    result, d = super().get_search_results(request, result, sub_term)
                    search_done = True
                    may_have_duplicates &= d
        if search_done and not request.GET.get(ORDER_VAR):
            result = self.sort_search_results(request, result, search_term, sub_terms)
        return result, may_have_duplicates

    def sort_search_results(self, request, queryset: QuerySet, search_term: str, sub_terms: list[str]) -> QuerySet:
        cases: list[When] = []
        max_points = len(sub_terms) * len(self.search_fields)
        matchers = ['iexact', 'istartswith', 'icontains']
        for x, matcher in enumerate(matchers, start=1):
            base_points = (len(matchers) - x) * max_points
            for i, term in enumerate(sub_terms):
                for j, field in enumerate(self.get_search_fields(request)):
                    if field.startswith('=') or field.endswith('__iexact'):
                        if matcher not in ['iexact']:
                            continue
                    if field.startswith('^') or field.endswith('__istartswith'):
                        if matcher not in ['iexact', 'istartswith']:
                            continue
                    field = field \
                        .removeprefix('=') \
                        .removeprefix('^') \
                        .removeprefix('@') \
                        .removesuffix('__iexact') \
                        .removesuffix('__istartswith') \
                        .removesuffix('__icontains') \
                        .removesuffix('__search')
                    points = base_points + (len(sub_terms) - i) * len(self.search_fields) - j
                    cases.append(When(**{f'{field}__{matcher}': term, 'then': points}))
        # Here using annotate instead of alias avoids repeating the case when clause three times in the query
        return queryset.annotate(
            _match_points=Max(
                Case(
                    *cases,
                    default=0,
                )
            )
        ).order_by('-_match_points')

    def save_related(self, request: HttpRequest, form, formsets, change: bool):
        super().save_related(request, form, formsets, change)
        self.after_save_related(request, form, formsets, change)

    def after_save_related(self, request: HttpRequest, form, formsets, change: bool):
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
        if self.data_type is bool and value in ('True', 'False'):
            value = value == 'True'
        return queryset.filter(self.filter(self.data_type(value))).distinct()

    def filter(self, value: data_type) -> Q:
        raise NotImplementedError()

    def get_facet_counts(self, pk_attname, filtered_qs):
        counts = {}
        for i, choice in enumerate(self.lookup_choices):
            counts[f'{i}__c'] = Count(
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


class AbstractCountFilter(CustomFilter):
    field_name: str
    title: str
    parameter_name: str
    soft_max_count: int
    min_count: int = 0

    def __init__(self, request, params: dict[str, str], model, model_admin):
        self.one_more_than_max = self.soft_max_count + 1
        self.one_more_than_max_display = f'{self.one_more_than_max}+'
        if not self.parameter_name:
            self.parameter_name = self.field_name
        if not self.title:
            self.title = self.field_name.replace('_', ' ')
        super().__init__(request, params, model, model_admin)

    def lookups(self, request, model_admin):
        return [(i, str(i)) for i in range(self.min_count, self.one_more_than_max)] + [(self.one_more_than_max_display, self.one_more_than_max_display)]

    def filter(self, value: str) -> Q:
        match value:
            case self.one_more_than_max_display:
                return Q(**{f'{self.field_name}__gte': self.one_more_than_max})
            case _:
                return Q(**{f'{self.field_name}': int(value)})


class CardCountListFilter(AbstractCountFilter):
    field_name = 'card_count'
    soft_max_count = DEFAULT_CARD_LIMIT
    min_count = 1


class IngredientCountListFilter(AbstractCountFilter):
    field_name = 'ingredient_count'
    soft_max_count = 9
    min_count = 1
