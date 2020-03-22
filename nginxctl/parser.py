import argparse
import sys
from functools import reduce

from boltons.iterutils import remap


def make_directive(args=None, directive=None, block=None, line=None, level=None):
    return {
        'args': args or [],
        'directive': directive or None,
        'block': block or [],
        'line': line or None
    }


def get_nested_dict(obj, path):
    return reduce(lambda o, n: o['block'][n], path, obj)


def get_nested_list(obj, path):  # assert len(path) > 0
    return reduce(lambda o, n: o[n]['block'], path, obj['block'])


def insert_into(obj, path, value, key):
    block = get_nested_list(obj, path[:-1])
    try:
        directive = block[path[-1]]
    except IndexError:
        block.append(make_directive(**{key: value}))
        return
    if not directive[key]:
        directive[key] = value
    else:
        block.append(make_directive(**{key: value}))


def parse_cli_config(argv=None):
    p, top_d, idx, last_idx = [], make_directive(), 0, 0
    argv = tuple(argv or sys.argv[1:])

    while idx < len(argv):
        arg = argv[idx]
        if arg == '-{':
            p.append(-1)

        elif arg in frozenset(('-b', '--block')):
            idx += 1
            arg = argv[idx]
            if idx == 1:
                top_d['directive'] = arg.lstrip('--')
            else:
                insert_into(top_d, p, arg.lstrip('--'), 'directive')

            if not argv[idx + 1].startswith('--'):
                idx += 1
                insert_into(top_d, p, [argv[idx]], 'args')

            p.append(-1)

        elif arg == '-}':
            p.pop(-1)

        else:
            if arg.startswith('--'):
                key = 'directive'
                arg = arg.lstrip('--')
            else:
                key = 'args'
                arg = [arg]
            insert_into(top_d, p, arg, key)
        idx += 1
    if p:
        raise argparse.ArgumentTypeError('Imbalanced {}')

    return remap(top_d, visit=lambda p, k, v: v != [] and k != '_level')


__all__ = ['parse_cli_config']
