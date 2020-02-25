from collections import deque
from itertools import islice
from pprint import PrettyPrinter

it_consumes = lambda it, n=None: deque(it, maxlen=0) if n is None else next(islice(it, n, n), None)
pp = PrettyPrinter(indent=4).pprint


def update_d(d, arg=None, **kwargs):
    if arg:
        d.update(arg)
    if kwargs:
        d.update(kwargs)
    return d


def del_keys_d(d, *keys, key=None, ignore_errors=True):
    remove = (d.__delitem__ if key in d else lambda i: i) if ignore_errors else d.__delitem__
    for key in keys:
        remove(key)
    if key is not None:
        remove(key)
    return d


def upsert_block():
    raise NotImplemented()


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
    elif isinstance(obj, (str, bytes, int)):
        pass
    else:
        raise NotImplementedError('get_dict_by_key_val for {!r} {}'.format(type(obj), obj))


def get_dict_by_key_va(obj, key, val):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and v == val:
                print('obj:'.ljust(20), obj)
                return obj
            elif isinstance(obj, (list, tuple, dict)):
                r = get_dict_by_key_val(obj, key, val)
                if isinstance(r, dict):
                    return r
            else:
                print('unexpectedly got type:', type(obj))
    elif isinstance(obj, (list, tuple)):
        for elem in obj:
            r = get_dict_by_key_val(elem, key, val)
            if isinstance(r, dict):
                print('returning:'.ljust(20), r)
                return r
    else:
        raise NotImplementedError('get_dict_by_key_val for {!r}'.format(type(obj)))


def filter_map_block(ds, *filter_callback_tuples):
    """
    Example:

    Replace listen port when 'localhost' is `server_name` and change `server_name` to 'example.com'
    >>> import crossplane
    >>> filter_map_block( \
        crossplane.parse('/etc/nginx/nginx.conf'), \
        ((lambda block: all((isinstance(block, dict), \
                             block.get_dict_by_key_val('directive', '') == 'server_name', \
                             block['args'] == ['localhost']))), \
         lambda block: replace_attr(block, 'args', ['example.com'])), \
        ((lambda block: all((isinstance(block, dict), \
                             block.get_dict_by_key_val('directive', '') == 'listen', \
                             block['args'] == ['80']))), \
         lambda block: replace_attr(block, 'args', ['8080'])) \
    )
    ```

    :param ds:
    :param filter_callback_tuples:
    :return:
    """

    # TODO: Make iteration O(n); then optimise until it's exactly n iterations. E.g., operator fusion

    def apply_matching_functions(directive):
        def process(block):
            if isinstance(block, dict):
                for filter_by, callback in filter_callback_tuples:
                    if filter_by(block):
                        old_block = block.copy()
                        block.clear()
                        block.update(callback(old_block))
                if 'block' in block:
                    return process(block['block'])
            elif isinstance(block, list):
                block = [process(block) for block in block]
            return block

        return process(directive)

    return type(ds)(apply_matching_functions(directive)
                    if 'block' in directive
                    else directive
                    for directive in ds)
