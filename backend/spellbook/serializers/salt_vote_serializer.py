from rest_framework import serializers
from spellbook.models import SaltVote, MAX_SALT


class SaltVoteSerializer(serializers.ModelSerializer):
    variant = serializers.CharField(source='variant_id', read_only=True)
    score = serializers.IntegerField(min_value=0, max_value=MAX_SALT)
    average = serializers.FloatField(read_only=True, min_value=0, max_value=MAX_SALT, allow_null=True, help_text='Average score of the recent votes on the variant, however few')
    vote_count = serializers.IntegerField(read_only=True, min_value=0, help_text='Number of recent votes on the variant')

    class Meta:
        model = SaltVote
        fields = [
            'variant',
            'score',
            'created',
            'updated',
            'average',
            'vote_count',
        ]
