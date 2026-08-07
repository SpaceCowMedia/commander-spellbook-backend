import re
from dataclasses import dataclass, field
from django.core.exceptions import ValidationError
from django.db.models import Exists, Model, OuterRef, Q
from spellbook.models import Card, CardInVariant, FeatureProducedByVariant, TemplateInVariant, Variant, VariantAlias


_QUOTED_OR_SHORT_VALUE_REGEX = r'"(?P<long_value>(?:[^"\\]|\\")+)"|(?P<short_value>.+)'
QUERY_VALUE_PATTERN = re.compile(r'(?P<prefix>all-|@)?(?P<key>[a-zA-Z_]+)(?P<operator><=|>=|:|=|<|>)(?:' + _QUOTED_OR_SHORT_VALUE_REGEX + r')', re.IGNORECASE)
SHORT_QUERY_VALUE_PATTERN = re.compile(_QUOTED_OR_SHORT_VALUE_REGEX, re.IGNORECASE)

# How a condition on each searchable model reaches the variant it is being tested against. Variant
# maps to nothing: a condition on it is a predicate on the row, not a subquery. A model missing from
# here raises rather than silently behaving like Variant.
CORRELATIONS: dict[type[Model], str] = {
    Variant: '',
    Card: 'cardinvariant__variant_id',
    CardInVariant: 'variant_id',
    TemplateInVariant: 'variant_id',
    FeatureProducedByVariant: 'variant_id',
    VariantAlias: 'variant_id',
}


@dataclass(frozen=True)
class QueryValue:
    prefix: str
    key: str
    operator: str
    value: str
    quotes: bool

    def is_for_all_related(self) -> bool:
        match self.prefix.lower():
            case '':
                return False
            case '@' | 'all-':
                return True
            case _:
                raise ValidationError(f'Prefix {self.prefix} is not supported for {self.key} search.')

    @classmethod
    def from_string(cls, string: str) -> 'QueryValue':
        match QUERY_VALUE_PATTERN.fullmatch(string):
            case None:
                raise ValidationError(f'Invalid query value: {string}')
            case match:
                quotes = bool(match['long_value'])
                return cls(match['prefix'] or '', match['key'], match['operator'], match['long_value'] if quotes else match['short_value'], quotes)

    @classmethod
    def from_short_string(cls, string: str, key: str, operator: str) -> 'QueryValue':
        match SHORT_QUERY_VALUE_PATTERN.fullmatch(string):
            case None:
                raise ValidationError(f'Invalid query value: {string}')
            case match:
                return cls('', key, operator, match['long_value'] or match['short_value'], quotes=True)  # Treat short values as quoted strings

    def to_filter(self, q: Q, model: type[Model] = Variant) -> 'VariantQuery':
        if self.is_for_all_related():
            # "every related row matches" is "no related row fails to match"
            return VariantQuery(node=VariantQueryFilter(~q, model, negated=True), leaves=1)
        return VariantQuery(node=VariantQueryFilter(q, model), leaves=1)

    def is_numeric(self) -> bool:
        return not self.quotes and self.value.isdigit()


@dataclass(frozen=True)
class VariantQueryFilter:
    '''One search condition, as a predicate on a Variant row.

    A condition on Variant itself is that predicate. A condition on any other model becomes a
    correlated EXISTS, because PostgreSQL keeps EXISTS cheap under OR and under negation while it
    degrades an `IN`/`NOT IN` subquery into a plain SubPlan re-executed for every candidate row.
    '''
    predicate: Q
    model: type[Model] = Variant
    negated: bool = False

    def negate(self) -> 'Node':
        return VariantQueryFilter(self.predicate, self.model, not self.negated)

    def to_q(self) -> Q:
        match CORRELATIONS[self.model]:
            case '':
                q = self.predicate
            case correlation:
                q = Q(Exists(self.model._default_manager.filter(self.predicate, **{correlation: OuterRef('pk')})))
        return ~q if self.negated else q


def combine(operands: 'tuple[Node, ...]', conjunction: bool) -> Q:
    '''Combines operands, first fusing the conditions that can share one subquery.

    A disjunction of conditions on the same model is one condition over the disjoined predicate,
    since an existential distributes over OR, and by De Morgan so is a conjunction of negated ones.
    The reverse never holds: `card:a card:b` needs two distinct cards, so conditions that are not
    negated stay apart under AND. Fusing matters most when an OR sits under an AND, where every
    extra subquery is re-run per candidate row.
    '''
    fusable: dict[type[Model], VariantQueryFilter] = {}
    rest: list[Q] = []
    for operand in operands:
        match operand:
            case VariantQueryFilter(model=model, negated=negated) if negated == conjunction:
                fused = fusable.get(model)
                fusable[model] = operand if fused is None else VariantQueryFilter(fused.predicate | operand.predicate, model, negated)
            case _:
                rest.append(operand.to_q())
    result: Q | None = None
    for q in [operand.to_q() for operand in fusable.values()] + rest:
        result = q if result is None else (result & q if conjunction else result | q)
    return Q() if result is None else result


@dataclass(frozen=True)
class Conjunction:
    operands: tuple['Node', ...] = ()

    def negate(self) -> 'Node':
        return disjunction(tuple(operand.negate() for operand in self.operands))

    def to_q(self) -> Q:
        return combine(self.operands, conjunction=True)


@dataclass(frozen=True)
class Disjunction:
    operands: tuple['Node', ...] = ()

    def negate(self) -> 'Node':
        return conjunction(tuple(operand.negate() for operand in self.operands))

    def to_q(self) -> Q:
        return combine(self.operands, conjunction=False)


Node = VariantQueryFilter | Conjunction | Disjunction


def flatten(node: Node, kind: 'type[Conjunction] | type[Disjunction]') -> tuple[Node, ...]:
    if isinstance(node, (Conjunction, Disjunction)) and isinstance(node, kind):
        return node.operands
    return (node,)


def normalize(operands: tuple[Node, ...], kind: 'type[Conjunction] | type[Disjunction]') -> tuple[Node, ...]:
    '''Splices nested operands of the same kind and drops repeats, since both AND and OR are
    associative and idempotent. Nesting has to go before anything else looks at the operands: a
    condition buried one level down is invisible to the fusion in `combine` and to `factor`.'''
    spliced = tuple(inner for operand in operands for inner in flatten(operand, kind))
    return tuple(dict.fromkeys(spliced))


def conjunction(operands: tuple[Node, ...]) -> Node:
    match normalize(operands, Conjunction):
        # A lone operand must not stay wrapped, or it hides from the fusion in `combine`.
        case (single,):
            return single
        case normalized:
            return Conjunction(normalized)


def disjunction(operands: tuple[Node, ...]) -> Node:
    match normalize(operands, Disjunction):
        case ():
            return Disjunction(())
        case (single,):
            return single
        case normalized:
            return factor(normalized)


def factor(operands: tuple[Node, ...]) -> Node:
    '''Lifts the conditions shared by every branch out of the disjunction.

    `(A AND B) OR (A AND C)` becomes `A AND (B OR C)`, which evaluates A once instead of once per
    branch, and puts B and C under a single OR where `combine` can fuse them into one subquery.
    A branch left with nothing is implied by the shared conditions alone, so the disjunction
    absorbs into them: `(A AND B) OR A == A`.
    '''
    branches = [flatten(operand, Conjunction) for operand in operands]
    common = tuple(node for node in branches[0] if all(node in branch for branch in branches[1:]))
    if not common:
        return Disjunction(operands)
    reduced = [tuple(node for node in branch if node not in common) for branch in branches]
    if any(not branch for branch in reduced):
        return conjunction(common)
    return conjunction(common + (disjunction(tuple(conjunction(branch) for branch in reduced)),))


@dataclass(frozen=True)
class VariantQuery:
    '''A boolean combination of search terms, reducible to a single Q over Variant.

    Negation is pushed down to the leaves as the tree is built, so every node is an AND or an OR of
    conditions and `combine` can fuse whatever shares a subquery.

    `guards` holds the conditions that qualify the term that produced them and must survive negation
    instead of being flipped by it. They stay factored out while terms are combined with AND, and
    are folded into each side by OR so that one branch's guard cannot silently constrain another's.
    '''
    node: Node = field(default_factory=Conjunction)
    guards: Q = field(default_factory=Q)
    leaves: int = 0

    def guarded_node(self) -> Node:
        if not self.guards:
            return self.node
        return conjunction((self.node, VariantQueryFilter(self.guards)))

    def __and__(self, other: 'VariantQuery') -> 'VariantQuery':
        return VariantQuery(
            node=conjunction((self.node, other.node)),
            guards=self.guards & other.guards,
            leaves=self.leaves + other.leaves,
        )

    def __or__(self, other: 'VariantQuery') -> 'VariantQuery':
        return VariantQuery(
            node=disjunction((self.guarded_node(), other.guarded_node())),
            leaves=self.leaves + other.leaves,
        )

    def __invert__(self) -> 'VariantQuery':
        return VariantQuery(node=self.node.negate(), guards=self.guards, leaves=self.leaves)

    def to_q(self) -> Q:
        return self.node.to_q() & self.guards


def guard(q: Q) -> VariantQuery:
    '''A condition that qualifies the term it belongs to rather than being part of what the user
    asked for, so negating the term must not flip it.'''
    return VariantQuery(guards=q, leaves=1)
