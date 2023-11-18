from rest_framework import serializers
from spellbook.models import Playable


class PricesSerializer(serializers.ModelSerializer):
    tcgplayer = serializers.DecimalField(source='price_tcgplayer', max_digits=10, decimal_places=2)
    cardkingdom = serializers.DecimalField(source='price_cardkingdom', max_digits=10, decimal_places=2)
    cardmarket = serializers.DecimalField(source='price_cardmarket', max_digits=10, decimal_places=2)

    class Meta:
        model = Playable
        fields = [
            'tcgplayer',
            'cardkingdom',
            'cardmarket',
        ]
