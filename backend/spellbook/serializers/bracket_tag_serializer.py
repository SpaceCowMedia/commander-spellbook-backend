from rest_framework import serializers
from spellbook.models import Variant
from spellbook.serializers.utils import WithOverrideMixin


class BracketTagSerializer(serializers.ChoiceField, WithOverrideMixin):
    def __init__(self, **kwargs):
        super().__init__(Variant.BracketTag.choices, **kwargs)
