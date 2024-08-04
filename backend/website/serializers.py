from rest_framework import serializers
from rest_framework_dataclasses.serializers import DataclassSerializer
from .models import WebsiteProperty
from .services.deck import Deck


class WebsitePropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = WebsiteProperty
        fields = ['key', 'value']


class DeckSerializer(DataclassSerializer):
    class Meta:
        dataclass = Deck
