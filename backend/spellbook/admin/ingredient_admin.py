from django.contrib.admin import TabularInline
from django.core.exceptions import ValidationError
from django.db.models import TextField, CharField
from django.forms import TextInput, Textarea
from adminsortable2.admin import SortableTabularInline
from django.http import HttpRequest
from spellbook.models import FeatureAttribute, FeatureOfCard, Ingredient
from spellbook.models.constants import MAX_ATTRIBUTE_VALUE_LENGTH
from spellbook.models.fields import DictionaryField
from spellbook.models.references import BUILT_IN_KEYS, references_to_features_not_needed
from spellbook.models.validators import PRODUCER_ATTRIBUTES_VALIDATOR
from .utils import DictionaryWidget, SpellbookAdminForm


def _textarea():
    return Textarea(attrs={'rows': 1, 'cols': 25, 'style': 'resize: vertical; min-height: 2em;'})


class IngredientForm(SpellbookAdminForm):
    def clean(self):
        if 'zone_locations' in self.cleaned_data:
            locations = self.cleaned_data['zone_locations']
            for location, state in Ingredient.CARD_STATE_FIELDS.items():
                if location not in locations:
                    self.cleaned_data[state] = ''
        return super().clean()

    class Meta:
        widgets = {state: _textarea() for state in Ingredient.CARD_STATE_FIELDS.values()}


class AttributesForm(SpellbookAdminForm):
    '''The form of a producer, whose dictionary is edited along with its attributes: an attribute is a
    key holding the text the producer provides under it, or nothing, saved with the attribute rather
    than in the dictionary.'''
    references_allowed = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['dictionary'].widget.attrs['data-tags'] = 'true'
        if self.instance.pk is not None:
            rows = self.instance.attributes.through.objects.filter(producer=self.instance).select_related('attribute').order_by('attribute__name')
            self.initial['dictionary'] = {**(self.instance.dictionary or {}), **{row.attribute.name: row.value or None for row in rows}}

    def clean_dictionary(self):
        dictionary = self.cleaned_data.get('dictionary') or {}
        PRODUCER_ATTRIBUTES_VALIDATOR(dictionary)
        values = {key: value or '' for key, value in dictionary.items() if key not in BUILT_IN_KEYS}
        if too_long := sorted(key for key, value in values.items() if len(value) > MAX_ATTRIBUTE_VALUE_LENGTH):
            raise ValidationError(f'An attribute holds at most {MAX_ATTRIBUTE_VALUE_LENGTH} characters, which these exceed: {", ".join(too_long)}.')
        if not self.references_allowed and (references := references_to_features_not_needed(values.values(), ())):
            raise ValidationError(f'A card feature cannot reference features, since it needs none: {", ".join(references)}.')
        self.cleaned_data['attribute_values'] = values
        return {key: value for key, value in dictionary.items() if key in BUILT_IN_KEYS}

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            self.save_attributes()
        else:
            save_m2m = self.save_m2m

            def save_all():
                save_m2m()
                self.save_attributes()
            self.save_m2m = save_all
        return instance

    def save_attributes(self):
        values = self.cleaned_data.get('attribute_values')
        if values is None:
            return
        attributes = dict(FeatureAttribute.objects.filter(name__in=values).values_list('name', 'id'))
        rows = self.instance.attributes.through.objects
        rows.filter(producer=self.instance).exclude(attribute_id__in=attributes.values()).delete()
        for name, value in values.items():
            rows.update_or_create(producer=self.instance, attribute_id=attributes[name], defaults={'value': value})


class DictionaryAdminInline(TabularInline):
    '''An inline whose rows hold a dictionary: its fields, then the dictionary, edited in a dialog of its own.'''
    formfield_overrides = {
        DictionaryField: {'widget': DictionaryWidget},
    }

    def get_fields(self, request: HttpRequest, obj=None):
        return [*(self.fields or ()), 'dictionary']


class WithFeatureAttributesAdminInline(DictionaryAdminInline):
    '''An inline of the rows producing a feature: the related object, its fields, then the dictionary
    edited along with the attributes the feature is produced with.'''
    form = AttributesForm
    related_field: str

    def get_fields(self, request: HttpRequest, obj=None):
        return [self.related_field, *super().get_fields(request, obj)]

    def get_autocomplete_fields(self, request: HttpRequest):
        return [self.related_field, *super().get_autocomplete_fields(request)]


class IngredientAdmin(TabularInline):
    form = IngredientForm
    extra = 0
    classes = ['ingredient']
    fields = [
        'quantity',
        'zone_locations',
        *Ingredient.CARD_STATE_FIELDS.values(),
        'must_be_commander',
    ]


class FeatureOfCardForm(AttributesForm, IngredientForm):
    references_allowed = False

    class Meta(IngredientForm.Meta):
        pass


class FeatureOfCardAdmin(WithFeatureAttributesAdminInline, IngredientAdmin):
    form = FeatureOfCardForm
    fields = [
        IngredientAdmin.fields[0],  # pyright: ignore[reportGeneralTypeIssues]
        'used_face',
        *IngredientAdmin.fields[1:],
        'is_mana_needed_an_accurate_minimum',
    ]
    model = FeatureOfCard
    formfield_overrides = {
        **WithFeatureAttributesAdminInline.formfield_overrides,
        CharField: {'widget': TextInput(attrs={'size': '12'})},
        TextField: {'widget': _textarea()},
    }


class OrderedIngredientAdmin(IngredientAdmin, SortableTabularInline):
    pass


class ComboIngredientAdmin(OrderedIngredientAdmin, DictionaryAdminInline):
    '''Sortable first, so that its order field comes after the dictionary.'''
