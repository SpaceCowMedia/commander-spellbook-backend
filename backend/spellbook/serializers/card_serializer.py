from rest_framework import serializers
from spellbook.models import Card


class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = [
            'id',
            'name',
            'oracle_id',
            'spoiler',
            'type_line',
            'image_uri_front_png',
            'image_uri_front_large',
            'image_uri_front_normal',
            'image_uri_front_small',
            'image_uri_back_png',
            'image_uri_back_large',
            'image_uri_back_normal',
            'image_uri_back_small',
        ]
