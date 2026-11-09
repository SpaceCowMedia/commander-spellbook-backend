from django.core.validators import EMPTY_VALUES
from django.core.exceptions import ValidationError
from django.db.models import JSONField
from django.forms import JSONField as JSONFormField, Widget


KEYWORDS_EMPTY_VALUES = [value for value in EMPTY_VALUES if not isinstance(value, list)]


class KeywordsFormField(JSONFormField):
    empty_values = KEYWORDS_EMPTY_VALUES

    def to_python(self, value):
        value = super().to_python(value)
        if value is None:
            return []
        return value

    def widget_attrs(self, widget: Widget) -> dict:
        return super().widget_attrs(widget) | {
            'rows': 1,
        }


def validate_keyword_json(value):
    if not isinstance(value, list):
        raise ValidationError(f'Keywords must be a list of strings, got {type(value).__name__}')
    for i, keyword in enumerate(value):
        if not isinstance(keyword, str):
            raise ValidationError(f'Keyword at position {i + 1} must be a string, got {type(keyword).__name__}')


class KeywordsField(JSONField):
    '''A list of strings stored as JSON, such as a card's keywords. An empty list is a valid value rather
    than a blank one, and every element has to be a string.'''
    empty_values = KEYWORDS_EMPTY_VALUES

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('default', list)
        super().__init__(*args, **kwargs)

    def validate(self, value, model_instance):
        super().validate(value, model_instance)
        validate_keyword_json(value)

    def formfield(self, **kwargs):
        return super().formfield(
            **{
                'form_class': KeywordsFormField,
                **kwargs,
            }
        )


DICTIONARY_EMPTY_VALUES = [value for value in EMPTY_VALUES if not isinstance(value, dict)]


class DictionaryFormField(JSONFormField):
    empty_values = DICTIONARY_EMPTY_VALUES

    def to_python(self, value):
        value = super().to_python(value)
        return {} if value is None else value


class DictionaryField(JSONField):
    '''A mapping of keys to a text or a list of texts stored as JSON, which the texts of a combo read
    with the [[feature@key]] syntax. An empty mapping is a valid value rather than a blank one. Every key
    but the built-in ones is a feature attribute, which the dictionary of a producer cannot hold, keeping
    its attributes apart.'''
    empty_values = DICTIONARY_EMPTY_VALUES

    def __init__(self, *args, attribute_keys: bool = True, **kwargs):
        from .validators import DICTIONARY_VALIDATOR, PRODUCER_DICTIONARY_VALIDATOR
        self.attribute_keys = attribute_keys
        kwargs.setdefault('default', dict)
        kwargs.setdefault('blank', True)
        kwargs.setdefault('verbose_name', 'dictionary')
        kwargs.setdefault('validators', [DICTIONARY_VALIDATOR if attribute_keys else PRODUCER_DICTIONARY_VALIDATOR])
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if not self.attribute_keys:
            kwargs['attribute_keys'] = False
        return name, path, args, kwargs

    def formfield(self, **kwargs):
        return super().formfield(
            **{
                'form_class': DictionaryFormField,
                **kwargs,
            }
        )
