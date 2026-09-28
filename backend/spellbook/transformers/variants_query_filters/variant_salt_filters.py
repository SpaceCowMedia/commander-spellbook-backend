from spellbook.models import MAX_SALT
from ..query_parsing import compare
from .base import QueryValue, VariantQuery


def salt_filter(qv: QueryValue) -> VariantQuery:
    salt = qv.decimal_value('salt', maximum=MAX_SALT)
    return qv.to_filter(compare('salt', qv.operator, salt))
