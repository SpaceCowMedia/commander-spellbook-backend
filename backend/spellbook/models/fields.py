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
