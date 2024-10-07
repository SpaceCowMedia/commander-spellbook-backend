from rest_framework import serializers
from spellbook.models import Combo


class ComboSerializer(serializers.ModelSerializer):
    class Meta:
        model = Combo
        fields = [
            'id',
        ]
