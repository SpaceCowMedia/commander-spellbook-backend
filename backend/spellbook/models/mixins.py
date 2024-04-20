from typing import Iterable, List, Sequence
from django.db.models import Model, Manager, QuerySet, JSONField
from django.utils.html import format_html
from rest_framework.serializers import ModelSerializer, BaseSerializer
from .scryfall import scryfall_query_string_for_card_names, scryfall_link_for_query


class ScryfallLinkMixin:
    def cards(self) -> list:
        raise NotImplementedError

    def query_string(self, cards: list | None = None):
        cards = cards or self.cards()
        return scryfall_query_string_for_card_names([card.name for card in cards])

    def scryfall_link(self):
        cards = self.cards()
        match cards:
            case []:
                return None
            case [card] if card.id is None:
                return None
            case _:
                link = scryfall_link_for_query(self.query_string(cards))
                plural = 's' if len(cards) > 1 else ''
                return format_html('<a href="{}" target="_blank">Show card{} on scryfall</a>', link, plural)


class PreSaveManager(Manager):
    use_in_migrations = True

    def bulk_create(self, objs: Iterable['PreSaveModelMixin'], *args, **kwargs) -> List:
        for obj in objs:
            obj.pre_save()
        return super().bulk_create(objs, *args, **kwargs)

    def bulk_update(self, objs: Iterable['PreSaveModelMixin'], fields: Sequence[str], *args, **kwargs) -> int:
        for obj in objs:
            obj.pre_save()
        return super().bulk_update(objs, fields, *args, **kwargs)


class PreSaveModelMixin(Model):
    objects = PreSaveManager()

    def pre_save(self) -> None:
        pass

    def save(self, *args, **kwargs) -> None:
        self.pre_save()
        return super().save(*args, **kwargs)

    class Meta:
        abstract = True
        base_manager_name = 'objects'


class PreSaveSerializedManager(PreSaveManager):
    def get_queryset(self) -> QuerySet:
        return super().get_queryset().defer('serialized')

    def bulk_serialize(self, objs: Iterable['PreSaveSerializedModelMixin'], serializer: type[ModelSerializer], *args, **kwargs) -> int:
        objs = list(objs)
        for obj in objs:
            obj.update_serialized(serializer)
        fields: list = kwargs.pop('fields', [])
        if 'serialized' not in fields:
            fields.append('serialized')
        return super(Manager, self).bulk_update(objs, *args, fields=fields, **kwargs)


class SerializedObjectsManager(Manager):
    def get_queryset(self) -> QuerySet:
        return super().get_queryset().filter(serialized__isnull=False).only('serialized')


class PreSaveSerializedModelMixin(PreSaveModelMixin):
    objects = PreSaveSerializedManager()
    serialized_objects = SerializedObjectsManager()
    serialized = JSONField(null=True, blank=True, editable=False)

    def update_serialized(self, serializer: type[ModelSerializer]) -> None:
        self.serialized = serializer(self).data

    class Meta:
        abstract = True
        base_manager_name = 'objects'


class PreSerializedSerializer(BaseSerializer):
    def to_representation(self, instance: PreSaveSerializedModelMixin):
        return instance.serialized
