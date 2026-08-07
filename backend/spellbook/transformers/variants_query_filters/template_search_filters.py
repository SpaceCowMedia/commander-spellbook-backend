from spellbook.models import TemplateInVariant
from .base import QueryValue, VariantQuery, Q, ValidationError


def template_search_filter(qv: QueryValue) -> VariantQuery:
    value_is_digit = qv.is_numeric()
    if value_is_digit and qv.is_for_all_related():
        raise ValidationError(f'Prefix {qv.prefix} is not supported for template search with numbers.')
    match qv.operator:
        case ':' if not value_is_digit:
            return qv.to_filter(Q(template__name__icontains=qv.value), TemplateInVariant)
        case '=' if not value_is_digit:
            return qv.to_filter(Q(template__name__iexact=qv.value), TemplateInVariant)
        case '<' if value_is_digit:
            return qv.to_filter(Q(template_count__lt=qv.value))
        case '>' if value_is_digit:
            return qv.to_filter(Q(template_count__gt=qv.value))
        case '<=' if value_is_digit:
            return qv.to_filter(Q(template_count__lte=qv.value))
        case '>=' if value_is_digit:
            return qv.to_filter(Q(template_count__gte=qv.value))
        case ':' | '=' if value_is_digit:
            return qv.to_filter(Q(template_count=qv.value))
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for template search.')
