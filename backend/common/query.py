from typing import TypeVar
from collections import defaultdict
from dataclasses import dataclass
from django.db.models import Q, QuerySet, Model
from .itertools import roundrobin


T = TypeVar('T', bound=Model)


@dataclass(frozen=True)
class Filter:
    q: Q
    positive: bool


def get_field_from_q(q: Q) -> str:
    if q.connector == Q.OR:
        children = q.children[:1]
    else:
        children = q.children
    field: str | None = None
    for child in children:
        if isinstance(child, tuple):
            assert len(child) == 2
            assert isinstance(child[0], str)
            field_name = child[0].split('__')[0]
        else:
            assert isinstance(child, Q)
            field_name = get_field_from_q(child)
        if field is None:
            field = field_name
        else:
            assert field == field_name
    assert field is not None
    return field


def smart_apply_filters(base: QuerySet[T], q: list[Filter]) -> QuerySet[T]:
    '''
    This function avoids queries that would result in a cartesian product
    due to the use of the same table in multiple filters.
    Additionally, it attempts to use as few subqueries as possible.

    Parameters:
        base: QuerySet - the base queryset to be filtered
        q: list[tuple[Q, bool]] - a list of tuples, each containing a Q object and a boolean
            indicating whether the filter is positive or negative

    Returns:
        QuerySet - the filtered queryset
    '''
    table_map = defaultdict[str, int](lambda: 1)
    for table, aliases in base.query.table_map.items():
        table_map[table] = len(aliases)
    queryset = base
    grouped_q = defaultdict[str, list[tuple[Q, bool]]](list)
    for f in q:
        field_name = get_field_from_q(f.q)
        grouped_q[field_name].append((f.q, f.positive))
    for q_list in grouped_q.values():
        q_list.sort(key=lambda q: q[0].children)
    round_robin_q = roundrobin(*grouped_q.values())
    for query, is_positive in round_robin_q:
        candidate_queryset = queryset.filter(query) if is_positive else queryset.exclude(query)
        if any(len(aliases) > table_map[table] for table, aliases in candidate_queryset.query.table_map.items()):
            queryset = base.filter(pk__in=queryset.values('pk'))
            queryset = queryset.filter(query) if is_positive else queryset.exclude(query)
        else:
            queryset = candidate_queryset
    return queryset
