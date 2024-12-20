from .base import QueryValue, QueryFilter, VariantFilterCollection, Q, ValidationError


def id_filter(spellbook_id_value: QueryValue) -> VariantFilterCollection:
    match spellbook_id_value.operator:
        case ':' | '=':
            return VariantFilterCollection(
                variants_filters=(
                    QueryFilter(
                        q=Q(id__iexact=spellbook_id_value.value) | Q(aliases__id__iexact=spellbook_id_value.value),
                        negated=spellbook_id_value.is_negated(),
                    ),
                ),
            )
        case _:
            raise ValidationError(f'Operator {spellbook_id_value.operator} is not supported for spellbook id search.')
