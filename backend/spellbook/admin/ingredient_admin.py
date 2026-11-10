from django.contrib.admin import TabularInline
from django.core.exceptions import ValidationError
from django.db.models import TextField, CharField
from django.forms import TextInput, Textarea
from adminsortable2.admin import SortableTabularInline
from django.http import HttpRequest
from spellbook.models import Explanation, FeatureAttribute, FeatureOfCard, Ingredient
from spellbook.models.references import references_to_features_not_needed
from spellbook.models.validators import validate_attributes
from .utils import AttributesFormField, SpellbookAdminForm


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
    '''The form of a producer, editing the attributes it produces its feature with, each holding the text
    it provides under that attribute or nothing, saved on its relationships with them.'''
    references_allowed = True
    attribute_texts = AttributesFormField(required=False, initial=dict, label='attributes', help_text='The attributes this produces the feature with, each holding nothing or a text a combo needing the feature writes with the [[feature@attribute]] syntax.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk is not None:
            rows = self.instance.attributes.through.objects.filter(producer=self.instance).select_related('attribute').order_by('attribute__name')
            self.initial['attribute_texts'] = {row.attribute.name: row.value or None for row in rows}

    def clean_attribute_texts(self):
        attributes = self.cleaned_data.get('attribute_texts') or {}
        validate_attributes(attributes)
        texts = {name: text or '' for name, text in attributes.items()}
        if not self.references_allowed and (references := references_to_features_not_needed(texts.values(), ())):
            raise ValidationError(f'A card feature cannot reference features, since it needs none: {", ".join(references)}.')
        return texts

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
        texts = self.cleaned_data.get('attribute_texts')
        if texts is None:
            return
        attributes = dict(FeatureAttribute.objects.filter(name__in=texts).values_list('name', 'id'))
        rows = self.instance.attributes.through.objects
        rows.filter(producer=self.instance).exclude(attribute_id__in=attributes.values()).delete()
        for name, text in texts.items():
            rows.update_or_create(producer=self.instance, attribute_id=attributes[name], defaults={'value': text})


class WithFeatureAttributesAdminInline(TabularInline):
    '''An inline of the rows producing a feature: the related object, its fields, then the attributes the
    feature is produced with, edited in a dialog of their own.'''
    form = AttributesForm
    related_field: str
    formfield_overrides = {
        CharField: {'widget': TextInput(attrs={'size': '12'})},
        TextField: {'widget': _textarea()},
    }

    def get_fields(self, request: HttpRequest, obj=None):
        return [self.related_field, *(self.fields or ()), 'attribute_texts']

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
        'mana_needed',
        'is_mana_needed_an_accurate_minimum',
        *IngredientAdmin.fields[1:],
        *(field for field in Explanation.text_fields_with_references() if field != 'mana_needed'),
    ]
    model = FeatureOfCard


class OrderedIngredientAdmin(IngredientAdmin, SortableTabularInline):
    pass


class ComboIngredientAdmin(OrderedIngredientAdmin):
    fields = [*OrderedIngredientAdmin.fields, 'in_replacements']
