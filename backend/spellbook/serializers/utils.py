from rest_framework import serializers


class StringMultipleChoiceField(serializers.MultipleChoiceField):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.keys = {k: i for i, k in enumerate(self.choices.keys())}

    def to_internal_value(self, data):
        choices = {choice for choice in super().to_internal_value(data) if choice is not None}
        return ''.join(sorted(choices, key=lambda x: self.keys[x]))

    def to_representation(self, value):
        return list(sorted(super().to_representation(value), key=lambda x: self.keys[x]))
