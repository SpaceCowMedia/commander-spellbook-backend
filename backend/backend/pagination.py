from django.utils.translation import gettext_lazy as _
from django.utils.encoding import force_str
from django.template import loader
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.utils.urls import replace_query_param
from rest_framework.request import Request


class CustomPagination(LimitOffsetPagination):
    max_limit = 100
    count_query = False
    count_query_param = 'count'
    count_query_description = _('Set to true to enable count query. If false, count will be omitted.')
    no_count_template = 'rest_framework/pagination/previous_and_next.html'
    count = None

    def paginate_queryset(self, queryset, request: Request, view=None):
        self.request = request
        self.count_query = self.get_count_query(request)
        if self.count_query:
            return super().paginate_queryset(queryset, request, view=view)
        self.limit = self.get_limit(request)
        if self.limit is None:
            return None
        self.offset = self.get_offset(request)
        result = list(queryset[self.offset:self.offset + self.limit])  # type: ignore
        self.has_next = len(result) >= self.limit  # type: ignore
        self.has_prev = self.offset > 0
        if (self.has_next or self.has_prev) and self.no_count_template is not None:  # type: ignore
            self.display_page_controls = True
        return result

    def get_count_query(self, request: Request):
        try:
            return request.query_params.get(self.count_query_param, 'false').lower() == 'true'
        except AttributeError:
            return False

    def get_next_link(self):
        if self.count_query:
            return super().get_next_link()
        if not self.has_next:  # type: ignore
            return None
        url = self.request.build_absolute_uri()
        url = replace_query_param(url, self.limit_query_param, self.limit)
        offset = self.offset + self.limit  # type: ignore
        return replace_query_param(url, self.offset_query_param, offset)

    def to_html(self):
        if self.count_query:
            return super().to_html()
        template = loader.get_template(self.no_count_template)
        context = self.get_html_context()
        return template.render(context)

    def get_html_context(self):
        if self.count_query:
            return super().get_html_context()
        return {
            'previous_url': self.get_previous_link(),
            'next_url': self.get_next_link(),
            'page_links': [],
        }

    def get_schema_operation_parameters(self, view):
        parameters = super().get_schema_operation_parameters(view)
        parameters.append({
            'name': self.count_query_param,
            'required': False,
            'in': 'query',
            'description': force_str(self.count_query_description),
            'schema': {
                'type': 'boolean',
                'default': False,
            },
        })
        return parameters

    def get_paginated_response_schema(self, schema):
        schema = super().get_paginated_response_schema(schema)
        schema['properties']['count']['nullable'] = True
        return schema
