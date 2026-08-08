from dataclasses import dataclass
from django.core.exceptions import ValidationError
from django.db.models import Model
from ..variants_query_filters.base import QueryValue

COLOR_NAMES = {'C': 'colorless', 'W': 'white', 'U': 'blue', 'B': 'black', 'R': 'red', 'G': 'green'}
ENTITY = '{entity}'


@dataclass(frozen=True)
class Verb:
    '''Both forms of the verb a term is phrased with, so that negating the term stays a matter of
    picking the other one instead of rewording the whole sentence.'''
    affirmative: str
    negative: str


USE = Verb('use', 'do not use')
HAVE = Verb('have', 'do not have')
PRODUCE = Verb('produce', 'do not produce')
REQUIRE = Verb('require', 'do not require')
COST = Verb('cost', 'do not cost')
BE = Verb('are', 'are not')


def join(parts: tuple[str, ...], conjunction: bool, comma: bool = False) -> str:
    connective = 'and' if conjunction else 'or'
    match parts:
        case ():
            return ''
        case (only,):
            return only
        case (first, last) if not comma:
            return f'{first} {connective} {last}'
        case _:
            return f'{", ".join(parts[:-1])}, {connective} {parts[-1]}'


@dataclass(frozen=True)
class Predicate:
    '''One search term, as something the combos being described do or do not do.'''
    verb: Verb
    complement: str
    negated: bool = False
    mergeable: bool = True

    @property
    def leaves(self) -> int:
        return 1

    def negate(self) -> 'Explanation':
        return Predicate(self.verb, self.complement, not self.negated, self.mergeable)

    def text(self) -> str:
        return f'{self.verb.negative if self.negated else self.verb.affirmative} {self.complement}'


@dataclass(frozen=True)
class Junction:
    operands: tuple['Explanation', ...] = ()
    conjunction: bool = True

    @property
    def leaves(self) -> int:
        return sum(operand.leaves for operand in self.operands)

    def negate(self) -> 'Explanation':
        return Junction(tuple(operand.negate() for operand in self.operands), not self.conjunction)

    def text(self) -> str:
        shared = self.shared_verb_text()
        if shared is not None:
            return shared
        parts = tuple(operand.nested_text() if isinstance(operand, Junction) else operand.text() for operand in self.operands)
        grouped = any(isinstance(operand, Junction) for operand in self.operands)
        return join(parts, self.conjunction, comma=grouped)

    def nested_text(self) -> str:
        '''A group nested in another one is always of the other kind, since same-kind operands are
        spliced in as they are combined. Saying up front how many of its parts have to hold keeps
        the reader from having to guess where the group ends.'''
        pair = len(self.operands) == 2
        if self.conjunction:
            quantifier = 'both' if pair else 'all of'
        else:
            quantifier = 'either' if pair else 'any of'
        shared = self.shared_verb_text(quantifier)
        if shared is not None:
            return shared
        if pair:
            return f'{quantifier} {self.text()}'
        return f'({self.text()})'

    def shared_verb_text(self, quantifier: str = '') -> str | None:
        '''A verb every operand shares reads better said once: "use both a card named X and a card
        named Y". Under AND, shared negation becomes "neither ... nor ...", which English scopes the
        way the query means it; under OR it would not, so those terms stay spelled out one by one.'''
        first = self.operands[0] if self.operands else None
        if not isinstance(first, Predicate) or len(self.operands) < 2:
            return None
        if any(not isinstance(operand, Predicate) or not operand.mergeable or operand.verb != first.verb or operand.negated != first.negated for operand in self.operands):
            return None
        complements = tuple(operand.complement for operand in self.operands if isinstance(operand, Predicate))
        if first.negated:
            if not self.conjunction:
                return None
            return f'{first.verb.affirmative} neither {" nor ".join(complements)}'
        return ' '.join(part for part in (first.verb.affirmative, quantifier, join(complements, self.conjunction)) if part)


Explanation = Predicate | Junction
Entity = type[Model] | tuple[str, str]


def flatten(operand: Explanation, conjunction: bool) -> tuple[Explanation, ...]:
    if isinstance(operand, Junction) and operand.conjunction == conjunction:
        return operand.operands
    return (operand,)


def combine(left: Explanation, right: Explanation, conjunction: bool) -> Explanation:
    return Junction(flatten(left, conjunction) + flatten(right, conjunction), conjunction)


def sentence(explanation: Explanation) -> str:
    if explanation.leaves == 0:
        return 'All combos.'
    return f'Combos that {explanation.text()}.'


def quoted(value: str) -> str:
    return f'“{value}”'


def entity_names(entity: 'Entity') -> tuple[str, str]:
    '''What to call one and many of a searchable thing: how Django was told to name its model for
    people, or a given pair of names for the things the query language calls something of its own.'''
    if isinstance(entity, tuple):
        return entity
    return str(entity._meta.verbose_name), str(entity._meta.verbose_name_plural)


def about(qv: QueryValue, verb: Verb, entity: 'Entity', template: str) -> Explanation:
    '''"use a card with X in the name", or "use only cards with X in the name" when the term is
    prefixed to demand that every related row matches. The template names its subject with ENTITY
    and is worded to read the same in both numbers, so that filling the placeholder in is all it
    takes to say one or many. The plural form is left out of any shared verb, since a reader would
    take its "only" to cover everything else sharing that verb too.'''
    singular, plural = entity_names(entity)
    if qv.is_for_all_related():
        return Predicate(verb, f'only {template.replace(ENTITY, plural)}', mergeable=False)
    phrase = template.replace(ENTITY, singular)
    return Predicate(verb, f'{'an' if phrase.startswith(tuple('aeiou')) else 'a'} {phrase}')


def count(operator: str, value: str, singular: str, plural: str) -> str:
    noun = singular if value == '1' else plural
    match operator:
        case ':' | '=':
            return f'exactly {value} {noun}'
        case '<':
            return f'fewer than {value} {noun}'
        case '<=':
            return f'at most {value} {noun}'
        case '>':
            return f'more than {value} {noun}'
        case '>=':
            return f'at least {value} {noun}'
        case _:
            raise ValidationError(f'Operator {operator} is not supported.')


def amount(operator: str, value: str) -> str:
    match operator:
        case ':' | '=':
            return f'exactly {value}'
        case '<':
            return f'less than {value}'
        case '<=':
            return f'{value} or less'
        case '>':
            return f'more than {value}'
        case '>=':
            return f'{value} or more'
        case _:
            raise ValidationError(f'Operator {operator} is not supported.')


def color_names(colors: str) -> str:
    return join(tuple(COLOR_NAMES[color] for color in colors), conjunction=True)
