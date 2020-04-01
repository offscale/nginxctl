from collections import deque
from itertools import islice
from pprint import PrettyPrinter
from string import printable
from sys import version_info

string_types = (basestring,) if version_info.major == 2 else (str,)
pp = PrettyPrinter(indent=4).pprint

it_consumes = lambda it, n=None: deque(it, maxlen=0) if n is None else next(islice(it, n, n), None)
unquoted_str = lambda arg: arg.translate(str.maketrans(dict.fromkeys('\'"', '')))


def update_d(d, arg=None, **kwargs):
    if arg:
        d.update(arg)
    if kwargs:
        d.update(kwargs)
    return d


def del_keys_d(d, key=None, ignore_errors=True, *keys):
    remove = (d.__delitem__ if key in d else lambda i: i) if ignore_errors else d.__delitem__
    for key in keys:
        remove(key)
    if key is not None:
        remove(key)
    return d


def omit(d, no):
    return {k: v for k, v in d.items() if k != no}


def update_directive(directive, args, new_directive=None, new_args=None):
    def visit(p, key, value):
        if is_directive(value) and omit(value, 'line') == {'directive': directive,
                                                           'args': args}:
            value.update({'args': new_args or args,
                          'directive': new_directive or directive})
        return key, value

    return visit


def is_directive(obj):
    return isinstance(obj, dict) and obj.keys() == frozenset({'args', 'directive', 'line'})


def upsert_block():
    raise NotImplementedError()


def replace_attr(block, attr_name, new_attr):
    if attr_name not in block:
        return block
    block[attr_name] = new_attr
    return block


def replace_elem_in_attr(block, attr_name, replace, new_attr):
    if attr_name not in block:
        return block
    structure = getattr(block, attr_name)
    setattr(block, attr_name, type(structure)(new_attr if element == replace else element
                                              for element in structure))
    return block


def get_dict_by_key_val(obj, key, value):
    if isinstance(obj, dict):
        if obj.get(key) == value:
            return obj
        for k, v in obj.items():
            val = get_dict_by_key_val(v, key, value)
            if val is not None:
                return val
    elif isinstance(obj, (tuple, list)):
        for val in obj:
            v = get_dict_by_key_val(val, key, value)
            if v is not None:
                return v
    elif isinstance(obj, string_types + (bytes, int)):
        pass
    else:
        raise NotImplementedError('get_dict_by_key_val for {!r} {}'.format(type(obj), obj))


def strings(filename, minimum=4):
    with open(filename, errors='ignore') as f:
        result = ''
        for c in f.read():
            if c in printable:
                result += c
                continue
            if len(result) >= minimum:
                yield result
            result = ''
        if len(result) >= minimum:  # catch result at EOF
            yield result
