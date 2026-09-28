from spellbook.models import MAX_SALT
from .base import QueryValue, Explanation, Predicate, HAVE, amount


def salt_explanation(qv: QueryValue) -> Explanation:
    salt = qv.decimal_value('salt', maximum=MAX_SALT)
    return Predicate(HAVE, f'an average salt score of {amount(qv.operator, f'{salt:f}')}')
