import itertools
from types import FunctionType


def listMethods(cls):
    return set(x for x, y in cls.__dict__.items() if isinstance(y, (FunctionType, classmethod, staticmethod)))


def listParentMethods(cls):
    return set(itertools.chain.from_iterable(
        listMethods(c).union(listParentMethods(c)) for c in cls.__bases__))


def list_subclass_methods(cls, is_narrow):
    methods = listMethods(cls)
    if is_narrow:
        parentMethods = listParentMethods(cls)
        return set(cls for cls in methods if not (cls in parentMethods))
    else:
        return methods


def count_methods(cls,):
    return len(list_subclass_methods(cls, is_narrow=False))
