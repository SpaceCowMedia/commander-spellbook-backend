from typing import TypeVar, Iterable
from itertools import cycle, islice


T = TypeVar('T')


def roundrobin(*iterables: Iterable[T]) -> Iterable[T]:
    '''
    Visit input iterables in a cycle until each is exhausted.

    .. code-block:: python
        roundrobin('ABC', 'D', 'EF') #--> A D E B F C

    Recipe credited to George Sakkis
    '''
    num_active = len(iterables)
    nexts = cycle(iter(it).__next__ for it in iterables)
    while num_active:
        try:
            for next in nexts:
                yield next()
        except StopIteration:
            # Remove the iterator we just exhausted from the cycle.
            num_active -= 1
            nexts = cycle(islice(nexts, num_active))
