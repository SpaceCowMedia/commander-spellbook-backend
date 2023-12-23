from rest_framework import serializers
from spellbook.models import Card


class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = ['id', 'name', 'oracle_id', 'spoiler']
