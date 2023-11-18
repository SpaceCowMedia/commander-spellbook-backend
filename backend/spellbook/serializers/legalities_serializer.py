from rest_framework import serializers
from spellbook.models import Playable


class LegalitiesSerializer(serializers.ModelSerializer):
    commander = serializers.BooleanField(source='legal_commander')
    pauper_commander_main = serializers.BooleanField(source='legal_pauper_commander_main')
    pauper_commander = serializers.BooleanField(source='legal_pauper_commander')
    oathbreaker = serializers.BooleanField(source='legal_oathbreaker')
    predh = serializers.BooleanField(source='legal_predh')
    brawl = serializers.BooleanField(source='legal_brawl')
    vintage = serializers.BooleanField(source='legal_vintage')
    legacy = serializers.BooleanField(source='legal_legacy')
    modern = serializers.BooleanField(source='legal_modern')
    pioneer = serializers.BooleanField(source='legal_pioneer')
    standard = serializers.BooleanField(source='legal_standard')
    pauper = serializers.BooleanField(source='legal_pauper')

    class Meta:
        abstract = True
        model = Playable
        fields = [
            'commander',
            'pauper_commander_main',
            'pauper_commander',
            'oathbreaker',
            'predh',
            'brawl',
            'vintage',
            'legacy',
            'modern',
            'pioneer',
            'standard',
            'pauper',
        ]
