from django.core.exceptions import ValidationError as DjangoValidationError
from djangorestframework_camel_case.render import CamelCaseJSONRenderer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from spellbook.transformers.variants_query_explanation_transformer import variants_query_explainer
from .filters import SpellbookQueryExplanationFilter
from .utils import FilterFormBrowsableAPIRenderer


class QueryExplanationSerializer(serializers.Serializer):
    q = serializers.CharField(allow_blank=True, help_text='The search query that was explained.')
    explanation = serializers.CharField(help_text='The search query, in plain English.')


class QueryExplanationView(APIView):
    permission_classes: list = []
    renderer_classes = [CamelCaseJSONRenderer, FilterFormBrowsableAPIRenderer]
    filter_backends = [SpellbookQueryExplanationFilter]
    response = QueryExplanationSerializer
    parameters = [
        OpenApiParameter(
            name=SpellbookQueryExplanationFilter.search_param,
            type=str,
            required=False,
            description=SpellbookQueryExplanationFilter.search_description,
        ),
    ]
    responses = {
        200: response,
        400: inline_serializer('QueryExplanationValidationError', {
            'q': serializers.ListSerializer(child=serializers.CharField(), required=False),
        }),
    }

    @extend_schema(parameters=parameters, responses=responses)
    def get(self, request: Request) -> Response:
        query = SpellbookQueryExplanationFilter().get_search_terms(request)
        try:
            explanation = variants_query_explainer(query)
        except DjangoValidationError as e:
            raise ValidationError(detail={SpellbookQueryExplanationFilter.search_param: e.messages}) from e
        serializer = self.response({'q': query, 'explanation': explanation})
        return Response(serializer.data)
