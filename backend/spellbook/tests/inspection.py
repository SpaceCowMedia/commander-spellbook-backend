import itertools
from types import FunctionType
from djangorestframework_camel_case.util import underscoreize
from types import SimpleNamespace


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
