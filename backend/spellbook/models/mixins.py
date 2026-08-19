from typing import Iterable, List, Sequence, TypeVar
from django.db.models import Model, Manager, QuerySet, CharField, JSONField
from django.utils.html import format_html
from rest_framework.serializers import ModelSerializer, BaseSerializer
from .scryfall import scryfall_query_string_for_card_names, scryfall_link_for_query

_T = TypeVar('_T', bound=Model)


class NamedModel(Model):
    '''Base for the models identified by a unique name, keeping track of the name they were loaded with
    so that a save can tell whether it is a rename, without querying for the stored one.'''

    @staticmethod
    def name_field(max_length: int = 255, **kwargs) -> CharField:
        '''Builds the name field, so that every child can adjust it without repeating the shared parts.'''
        return CharField(max_length=max_length, unique=True, blank=False, **kwargs)

    # only a default: every child overrides it with its own length, validators and descriptions
    name = name_field()
    _name: str | None = None

    class Meta:
        abstract = True

    @property
    def renamed_from(self) -> str | None:
        '''The name still stored in the database, empty unless this instance carries a pending rename.'''
        return self._name if self._name != self.name else None

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        # read from the loaded values, to avoid fetching the name when it is deferred
        instance._name = instance.__dict__.get('name')
        return instance

    def save(self, *args, **kwargs):
        result = super().save(*args, **kwargs)
        # the receivers of post_save ran against the old name, that is now the stored one
        self._name = self.name
        return result


class ScryfallLinkMixin:
    def cards(self) -> Iterable[str]:
        raise NotImplementedError

    def query_string(self):
        return scryfall_query_string_for_card_names(list(self.cards()))

    def scryfall_link(self, raw=False):
        cards = list(self.cards())
        match cards:
            case []:
                return None
            case _:
                link = scryfall_link_for_query(scryfall_query_string_for_card_names(cards))
                if raw:
                    return link
                plural = 's' if len(cards) > 1 else ''
                return format_html('<a href="{}" target="_blank">Show card{} on scryfall</a>', link, plural)


class PreSaveManager(Manager[_T]):
    def bulk_create(self, objs: Iterable[_T], skip_pre_save=False, *args, **kwargs) -> List[_T]:  # type: ignore[override]
        if not skip_pre_save:
            for obj in objs:
                obj.pre_save()  # type: ignore[attr-defined]
        return super().bulk_create(objs, *args, **kwargs)

    def bulk_update(self, objs: Iterable[_T], fields: Sequence[str], skip_pre_save=False, *args, **kwargs) -> int:  # type: ignore[override]
        if not skip_pre_save:
            for obj in objs:
                obj.pre_save()  # type: ignore[attr-defined]
        return super().bulk_update(objs, fields, *args, **kwargs)


class PreSaveModelMixin(Model):
    objects = PreSaveManager()

    def pre_save(self):
        pass

    def save(self, skip_pre_save=False, *args, **kwargs):
        if not skip_pre_save:
            self.pre_save()
        return super().save(*args, **kwargs)

    class Meta:
        abstract = True
        base_manager_name = 'objects'


class PreSaveSerializedManager(PreSaveManager[_T]):
    def get_queryset(self) -> QuerySet:
        return super().get_queryset().defer('serialized')

    def bulk_serialize(self, objs: Sequence['PreSaveSerializedModelMixin'], serializer: type[ModelSerializer], *args, **kwargs) -> int:
        fields: list = kwargs.pop('fields', [])
        if 'serialized' not in fields:
            fields.append('serialized')
        for obj in objs:
            obj.pre_save()
        for obj, data in zip(objs, serializer(objs, many=True).data):
            obj.serialized = dict(data)
        return super(Manager, self).bulk_update(objs, *args, fields=fields, **kwargs)  # type: ignore[misc]


class SerializedObjectsManager(Manager):
    def get_queryset(self) -> QuerySet:
        return super().get_queryset().filter(serialized__isnull=False).only('serialized')


class PreSaveSerializedModelMixin(PreSaveModelMixin):
    objects = PreSaveSerializedManager()  # type: ignore[misc]
    serialized_objects = SerializedObjectsManager()
    serialized = JSONField(null=True, blank=True, editable=False)

    def update_serialized(self, serializer: type[ModelSerializer]):
        self.serialized = dict(serializer(self).data)

    class Meta:
        abstract = True
        base_manager_name = 'objects'


class PreSerializedSerializer(BaseSerializer):
    def to_representation(self, instance: PreSaveSerializedModelMixin):
        return instance.serialized
