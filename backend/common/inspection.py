from itertools import chain
from types import FunctionType
from djangorestframework_camel_case.util import underscoreize
from types import SimpleNamespace


def list_methods(cls):
    return set(x for x, y in cls.__dict__.items() if isinstance(y, (FunctionType, classmethod, staticmethod)) and x not in ('__init__', '__annotate_func__'))


def list_parent_methods(cls):
    return set(chain.from_iterable(list_methods(c).union(list_parent_methods(c)) for c in cls.__bases__))


def list_subclass_methods(cls, is_narrow):
    methods = list_methods(cls)
    if is_narrow:
        parentMethods = list_parent_methods(cls)
        return methods.difference(parentMethods)
    else:
        return methods


def count_methods(cls,):
    return len(list_subclass_methods(cls, is_narrow=False))


def parse(data):
    if type(data) is list:
        return list(map(parse, data))
    elif type(data) is dict:
        sns = SimpleNamespace()
        for key, value in data.items():
            setattr(sns, key, parse(value))
        return sns
    else:
        return data


def json_to_python_lambda(d):
    d = underscoreize(d)
    return parse(d)
