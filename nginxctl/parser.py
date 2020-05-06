import argparse
import sys
from functools import reduce
from itertools import count

from boltons.iterutils import remap


def make_directive(args=None, directive=None, block=None, line=None):
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


def insert_into(obj, path, value, key, counter):
    block = get_nested_list(obj, path[:-1])
    try:
        directive = block[path[-1]]
    except IndexError:
        block.append(make_directive(**{key: value, 'line': next(counter)}))
        return
    if not directive[key]:
        directive[key] = value
    else:
        block.append(make_directive(**{key: value, 'line': next(counter)}))


def parse_args(args):
    if not isinstance(args, (list, tuple)):
        args = [args]
    if not len(args) == 1:
        return args

    stack, components = [], []
    for arg in args:
        for c in arg:
            if c == ' ':
                components.append(''.join(stack))
                stack.clear()
            else:
                stack.append(c)
    components.append(''.join(stack))

    return components


def parse_cli_config(argv=None):
    p, top_d, idx, c = [], make_directive(), 0, count()
    argv = tuple(argv or sys.argv[1:])

    while idx < len(argv):
        arg = argv[idx]

        if arg == '-{':
            p.append(-1)
            next(c)

        elif arg in frozenset(('-b', '--block')):
            next(c)
            idx += 1
            arg = argv[idx]
            if idx == 1:
                top_d.update({
                    'directive': arg.lstrip('--'),
                    'line': next(c)
                })
                if len(argv) > 2 and argv[3].startswith('--'):
                    top_d['args'] = parse_args(argv[2])
                    idx += 1
            else:
                insert_into(top_d, p, arg.lstrip('--'), 'directive', c)

            if not argv[idx + 1].startswith('--'):
                idx += 1
                insert_into(top_d, p, parse_args(argv[idx]), 'args', c)

            p.append(-1)

        elif arg == '-}':
            p.pop(-1)

        else:
            if arg.startswith('--'):
                key = 'directive'
                arg = arg.lstrip('--')
            else:
                key = 'args'
                arg = parse_args(arg)
            insert_into(top_d, p, arg, key, c)
        idx += 1
    if p:
        raise argparse.ArgumentTypeError('Imbalanced {}')

    return remap(top_d, visit=lambda _, k, v: (k, None if k == 'block' and not v else v))


def cli_to_context2block(cli_to_parse):
    context2block = {'http': [], 'server': []}
    left, left_added, context, stack = 0, 0, None, []
    for idx, arg in enumerate(cli_to_parse):
        if arg == '-b':
            left += 1
            left_added = idx
        elif arg == '-}':
            left -= 1
        elif left_added == idx - 1 and left == 1:
            if len(stack) == 0 and idx != 0:
                stack = [context2block[context][-1].pop()]
            context = arg if arg == 'server' else 'http'
            context2block[context].append(stack.copy())
            stack.clear()

        if context is not None:
            context2block[context][-1].append(arg)
        else:
            stack.append(arg)

    # Flatten. Later on we might want to generate different files, rather than one server.conf &etc. So unflatten then.
    return {context: [item for sublist in block for item in sublist]
            for context, block in context2block.items()}


__all__ = ['parse_cli_config', 'cli_to_context2block']
