from collections import defaultdict
from django.db.models import Q, QuerySet
from .itertools import roundrobin


def smart_apply_filters(base: QuerySet, q: list[tuple[Q, bool]]) -> QuerySet:
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
    for query, is_positive in q:
        field_name = query.children[0][0].split('__')[0]
        grouped_q[field_name].append((query, is_positive))
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
