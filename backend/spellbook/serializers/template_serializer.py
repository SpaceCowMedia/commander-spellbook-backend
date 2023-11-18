from django.db.models import QuerySet
from rest_framework import serializers
from spellbook.models import Template


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = ['id', 'name', 'scryfall_query', 'scryfall_api']

    @classmethod
    def prefetch_related(cls, queryset: QuerySet[Template]):
        return queryset.all()
