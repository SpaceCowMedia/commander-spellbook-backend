from rest_framework import serializers, fields


class StringMultipleChoiceField(serializers.MultipleChoiceField):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.keys = {k: i for i, k in enumerate(self.choices.keys())}

    def to_internal_value(self, data):
        choices = {choice for choice in super().to_internal_value(data) if choice is not None}
        return ''.join(sorted(choices, key=lambda x: self.keys[x]))  # type: ignore

    def to_representation(self, value):
        return list(sorted(super().to_representation(value), key=lambda x: self.keys[x]))


class WithOverrideMixin(serializers.Field):
    def get_attribute(self, instance):
        override_source = f'{self.source}_override'
        override_source_attrs = override_source.split('.')
        try:
            override_value = fields.get_attribute(instance, override_source_attrs)
        except (KeyError, AttributeError):
            override_value = None
        if override_value is not None:
            self.source = override_source
            self.source_attrs = override_source_attrs
            return super().get_attribute(instance)
        return super().get_attribute(instance)
