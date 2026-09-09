import re
from django.core.exceptions import ValidationError

# what a tilde stands for inside a regular expression: the card names itself on the line being matched
NAME_IN_REGEX = r'[^\n]+'

# a regular expression as a Scryfall query writes it: between two slashes, and directly after the
# operator of the term it is the value of, which is the only place the grammar allows one. Asking for
# the operator is what keeps the slashes of a +1/+1 in quoted card text from reading as a pattern.
REGEX_VALUE_PATTERN = re.compile(r'(?<=[:=<>])/((?:\\/|[^/])+)/')

MAX_REGEX_LENGTH = 256
MAX_REPETITION = 64

QUANTIFIERS = '*+?'
LAZY_OR_POSSESSIVE = '?+'


def expand_card_name(pattern: str) -> str:
    '''The pattern as it will be run, with the tilde a query writes for the card's own name filled in.'''
    return pattern.replace('~', NAME_IN_REGEX)


def end_of_class(pattern: str, start: int) -> int:
    '''The position just past the character class opening at `start`.'''
    position = start + 1
    if position < len(pattern) and pattern[position] == '^':
        position += 1
    # a class may open with a literal closing bracket
    if position < len(pattern) and pattern[position] == ']':
        position += 1
    while position < len(pattern) and pattern[position] != ']':
        position += 2 if pattern[position] == '\\' else 1
    return min(position + 1, len(pattern))


def exclude_newline(pattern: str) -> str:
    '''The pattern with every negated class told not to match a newline, which PostgreSQL does itself.'''
    read = []
    position = 0
    while position < len(pattern):
        if pattern[position] == '\\':
            read.append(pattern[position:position + 2])
            position += 2
        elif pattern[position] == '[':
            end = end_of_class(pattern, position)
            body = pattern[position:end]
            read.append(f'{body[:-1]}\\n]' if body.startswith('[^') and body.endswith(']') else body)
            position = end
        else:
            read.append(pattern[position])
            position += 1
    return ''.join(read)


def read_quantifier(pattern: str, start: int) -> tuple[int, bool]:
    '''The position past a quantifier at `start`, and whether one was there at all.

    A brace only opens a repetition when a digit follows it. Everything else is a literal, which is how
    a query writes a mana symbol such as {T} without escaping it.'''
    if start >= len(pattern):
        return start, False
    if pattern[start] in QUANTIFIERS:
        position = start + 1
        if position < len(pattern) and pattern[position] in LAZY_OR_POSSESSIVE:
            position += 1
        return position, True
    if pattern[start] == '{' and start + 1 < len(pattern) and pattern[start + 1].isdigit():
        end = pattern.find('}', start)
        if end < 0:
            return start, False
        for bound in pattern[start + 1:end].split(','):
            if bound.isdigit() and int(bound) > MAX_REPETITION:
                raise ValidationError(f'A regular expression may not repeat anything more than {MAX_REPETITION} times.')
        position = end + 1
        if position < len(pattern) and pattern[position] in LAZY_OR_POSSESSIVE:
            position += 1
        return position, True
    return start, False


def validate_safe_regex(pattern: str):
    '''Refuses a regular expression that could take exponential time to match.

    Catastrophic backtracking needs a quantifier over a subexpression able to match the same text in
    more than one way, which is a quantified group holding another quantifier or an alternation: (a+)+
    and (a|a)* are the shapes of it. A bounded repetition is capped as well, since a large one multiplies
    the work without needing any nesting, and a back reference is refused outright, being the thing that
    forces a backtracking engine in the first place. Only a plain or non-capturing group is allowed: a
    lookaround is a search of its own, run at every position of the subject.'''
    if len(pattern) > MAX_REGEX_LENGTH:
        raise ValidationError(f'A regular expression must be at most {MAX_REGEX_LENGTH} characters long.')
    try:
        re.compile(pattern)
    except re.error as e:
        raise ValidationError(f'Invalid regular expression: {e}') from e
    enclosing: list[list[bool]] = []
    # whether the group being read holds a quantifier, and whether it holds an alternation
    group = [False, False]
    position = 0
    while position < len(pattern):
        character = pattern[position]
        if character == '(':
            if pattern[position:position + 2] == '(?':
                if pattern[position:position + 3] != '(?:':
                    raise ValidationError('Only plain and non-capturing groups are allowed in a regular expression.')
                position += 2
            enclosing.append(group)
            group = [False, False]
            position += 1
            continue
        if character == '|':
            group[1] = True
            position += 1
            continue
        if character == ')':
            inner = group
            group = enclosing.pop() if enclosing else [False, False]
            position, quantified = read_quantifier(pattern, position + 1)
            if quantified:
                if inner[0] or inner[1]:
                    raise ValidationError('A regular expression may not repeat a group that repeats or chooses within itself.')
                group[0] = True
            continue
        if character == '\\':
            if position + 1 < len(pattern) and pattern[position + 1].isdigit():
                raise ValidationError('Back references are not allowed in a regular expression.')
            position += 2
        elif character == '[':
            position = end_of_class(pattern, position)
        else:
            position += 1
        position, quantified = read_quantifier(pattern, position)
        if quantified:
            group[0] = True


def validate_query_regexes(query: str):
    '''Refuses a Scryfall query holding a regular expression that could take exponential time to match.

    The query is scanned rather than parsed, so that a value only looking like a regular expression is
    checked too: reading a safe one that was never going to run costs nothing, and this way the check
    does not depend on the query parsing in the first place.'''
    for match in REGEX_VALUE_PATTERN.finditer(query):
        validate_safe_regex(expand_card_name(match.group(1)))
