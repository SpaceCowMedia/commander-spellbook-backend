from .models import Card, Feature, Combo, Template, Variant
from .serializers import CardDetailSerializer, FeatureSerializer, ComboDetailSerializer, TemplateSerializer, VariantSerializer
from rest_framework import viewsets


class VariantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Variant.objects.filter(status=Variant.Status.OK)
    serializer_class = VariantSerializer
    # filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # filterset_fields = ['unique_id', 'uses__id', 'includes__id', 'produces__id', 'of__id', 'identity']
    # search_fields = ['uses__name', 'produces__name']
    # ordering_fields = ['created', 'updated', 'unique_id']


variant_list = VariantViewSet.as_view({'get': 'list'})
variant_detail = VariantViewSet.as_view({'get': 'retrieve'})


class FeatureViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Feature.objects.all()
    serializer_class = FeatureSerializer


feature_list = FeatureViewSet.as_view({'get': 'list'})
feature_detail = FeatureViewSet.as_view({'get': 'retrieve'})


class ComboViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Combo.objects.all()
    serializer_class = ComboDetailSerializer


combo_list = ComboViewSet.as_view({'get': 'list'})
combo_detail = ComboViewSet.as_view({'get': 'retrieve'})


class CardViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Card.objects.all()
    serializer_class = CardDetailSerializer
    filterset_fields = ['oracle_id', 'identity']


card_list = CardViewSet.as_view({'get': 'list'})
card_detail = CardViewSet.as_view({'get': 'retrieve'})


class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Template.objects.all()
    serializer_class = TemplateSerializer


template_list = TemplateViewSet.as_view({'get': 'list'})
template_detail = TemplateViewSet.as_view({'get': 'retrieve'})
