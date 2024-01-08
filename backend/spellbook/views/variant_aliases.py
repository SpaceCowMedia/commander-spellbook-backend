from rest_framework import viewsets
from spellbook.models import VariantAlias
from spellbook.serializers import VariantAliasSerializer


class VariantAliasViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VariantAlias.objects.all()
    serializer_class = VariantAliasSerializer
