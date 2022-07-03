from .models import Card, Feature, Combo, Variant
from .serializers import CardSerializer, FeatureSerializer, ComboSerializer, VariantSerializer
from rest_framework import viewsets

class VariantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Variant.objects.filter(status=Variant.Status.OK)
    serializer_class = VariantSerializer

variant_list = VariantViewSet.as_view({'get': 'list'})
variant_detail = VariantViewSet.as_view({'get': 'retrieve'})

class FeatureViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Feature.objects.all()
    serializer_class = FeatureSerializer

feature_list = FeatureViewSet.as_view({'get': 'list'})
feature_detail = FeatureViewSet.as_view({'get': 'retrieve'})

class ComboViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Combo.objects.all()
    serializer_class = ComboSerializer

combo_list = ComboViewSet.as_view({'get': 'list'})
combo_detail = ComboViewSet.as_view({'get': 'retrieve'})

class CardViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Card.objects.all()
    serializer_class = CardSerializer

card_list = CardViewSet.as_view({'get': 'list'})
card_detail = CardViewSet.as_view({'get': 'retrieve'})
