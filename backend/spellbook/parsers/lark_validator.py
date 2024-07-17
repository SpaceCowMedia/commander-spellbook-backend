from lark import Lark, UnexpectedInput
from django.utils.deconstruct import deconstructible
from django.core.exceptions import ValidationError


@deconstructible
class LarkGrammarValidator:
    parser: Lark
    message = 'Invalid syntax at character %(column)s'
    code = 'invalid'

    def __init__(
        self, grammar: str, parser='lalr', message: str | None = None, code: str | None = None
    ):
        self.parser = Lark(grammar, parser=parser)
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code

    def __call__(self, value):
        try:
            self.parser.parse(value)
        except UnexpectedInput as e:
            raise ValidationError(self.message, code=self.code, params={'column': e.column}) from e
