from itertools import zip_longest
from django.db.models import Model
from django.db.models.manager import BaseManager
from rest_framework import serializers, fields
from spellbook.models import DEFAULT_BATCH_SIZE


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


class ModelSerializerWithRelatedModels:
    related_field: str

    def _create_related_model(
        self,
        instance,
        manager: BaseManager,
        data: list[dict],
        with_order: bool = True,
    ):
        to_create: list[Model] = []
        for i, d in enumerate(data, start=1):
            if with_order:
                d['order'] = i
            to_create.append(manager.model(**{**d, self.related_field: instance}))
        manager.bulk_create(to_create, batch_size=DEFAULT_BATCH_SIZE)

    def _update_related_model(
        self,
        instance,
        manager: BaseManager,
        data: list[dict],
        serializer: serializers.ModelSerializer,
        with_order: bool = True,
    ):
        to_create: list[Model] = []
        to_update: list[Model] = []
        to_delete = []
        models = manager.order_by('order') if with_order else manager.all()
        for i, (d, model) in enumerate(zip_longest(data, models), start=1):
            if d is not None and with_order:
                d['order'] = i
            if model is None:
                to_create.append(manager.model(**{**d, self.related_field: instance}))
            elif d is None:
                to_delete.append(model.pk)
            else:
                for key, value in d.items():
                    setattr(model, key, value)
                to_update.append(model)
        manager.bulk_create(to_create, batch_size=DEFAULT_BATCH_SIZE)
        manager.bulk_update(to_update, serializer.fields.keys(), batch_size=DEFAULT_BATCH_SIZE)  # type: ignore
        for batch_start in range(0, len(to_delete), DEFAULT_BATCH_SIZE):
            manager.filter(pk__in=to_delete[batch_start:batch_start + DEFAULT_BATCH_SIZE]).delete()
