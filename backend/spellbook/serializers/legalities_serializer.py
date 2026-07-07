from rest_framework import serializers
from spellbook.models import Playable


class LegalitiesSerializer(serializers.ModelSerializer):
    commander = serializers.BooleanField(source='legal_commander')
    pauper_commander_main = serializers.BooleanField(source='legal_pauper_commander_main')
    pauper_commander = serializers.BooleanField(source='legal_pauper_commander')
    oathbreaker = serializers.BooleanField(source='legal_oathbreaker')
    predh = serializers.BooleanField(source='legal_predh')
    standard_brawl = serializers.BooleanField(source='legal_standard_brawl')
    brawl = serializers.BooleanField(source='legal_brawl')
    competitive_brawl = serializers.BooleanField(source='legal_competitive_brawl')
    alchemy = serializers.BooleanField(source='legal_alchemy')
    vintage = serializers.BooleanField(source='legal_vintage')
    legacy = serializers.BooleanField(source='legal_legacy')
    premodern = serializers.BooleanField(source='legal_premodern')
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
            'standard_brawl',
            'brawl',
            'competitive_brawl',
            'alchemy',
            'vintage',
            'legacy',
            'premodern',
            'modern',
            'pioneer',
            'standard',
            'pauper',
        ]
