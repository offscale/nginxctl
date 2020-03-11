#!/usr/bin/env python

import argparse
import itertools
import os
import sys
from argparse import ArgumentParser
from enum import Enum
from functools import partial
from shutil import which

import toolz

from nginxctl import __version__
from nginxctl.helpers import it_consumes, pp, strings


class Command(Enum):
    serve = 'serve'
    emit = 'emit'
    dry_run = 'dry_run'

    def __str__(self):
        return self.value


# Slightly modified https://stackoverflow.com/a/11415816
class ReadableDir(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        def is_dir_readable(prospective_dir):
            if not os.path.isdir(prospective_dir):
                raise argparse.ArgumentTypeError("{!r} is not a valid path".format(prospective_dir))
            elif not os.access(prospective_dir, os.R_OK):
                raise argparse.ArgumentTypeError("{!r} is not a readable dir".format(prospective_dir))

        return it_consumes(map(is_dir_readable, values))


unquoted_str = lambda arg: arg.translate(str.maketrans(dict.fromkeys('\'"', '')))


def _build_parser():
    if 'GITHUB_ACTION' in os.environ:
        default_nginx, default_prefix, default_conf = '/usr/local/bin/nginx', '/usr/local/Cellar/nginx/1.17.9/', '/usr/local/etc/nginx/nginx.conf'
    else:
        default_nginx = which('nginx')
        default_nginx_usage = next(line
                                   for line in strings(default_nginx)
                                   if 'set prefix path' in line).split()
        default_prefix, default_conf = tuple(
            l[:-1]
            for i, l in enumerate(default_nginx_usage)
            if i > 0 and 'default' in default_nginx_usage[i - 1]
        )

    parser = ArgumentParser(
        prog='python -m nginxctl',
        description='Commands for modifying and controlling nginx over the command-line.',
        epilog='Example usage: %(prog)s -w \'/tmp/wwwroot\' -p 8080 -i \'192.168.2.1\' '
               '-w \'/mnt/webroot\' -p 9001 -i \'localhost\' --path \'/api\' --proxy-pass  \'192.168.2.1/api\''
    )
    # parser.add_argument('command', help='serve, emit, or dry_run', type=Command, choices=list(Command))

    parser.add_argument('--version', action='version', version='%(prog)s {}'.format(__version__))

    # parser.add_argument('--dns', help='DNS alias')
    # parser.add_argument('--ip', help='Public IP address', required=True)
    parser.add_argument('--listen', help='Listen (e.g., port)', default='8080', nargs='*')
    parser.add_argument('--prefix', help='set prefix path, e.g., {!r}'.format(default_prefix),
                        default=default_prefix)
    parser.add_argument('--config-filename',
                        help='Name of file. Placed in prefix folder—e.g., {!r}—if not absolute. E.g., nginx.conf'.format(
                            default_nginx),
                        default=default_nginx)
    parser.add_argument('--root', help='Root', nargs='*',
                        type=unquoted_str, action=ReadableDir, default=os.getcwd())
    parser.add_argument('--nginx',
                        help='Path to nginx binary, defaults to first in PATH, i.e., {!r}'.format(default_nginx),
                        dest='nginx', default=default_nginx)
    parser.add_argument('-b', '--block', dest='block', help='Block, e.g., server or http', type=str, nargs='*')

    # Pass along to the `nginx` process:
    parser.add_argument('-?', help=argparse.SUPPRESS, action='store_true')  # this help
    parser.add_argument('-V', help=argparse.SUPPRESS)  # show version and configure options then exit
    parser.add_argument('-t', help=argparse.SUPPRESS)  # test configuration and exit
    parser.add_argument('-T', help=argparse.SUPPRESS)  # test configuration, dump it and exit
    parser.add_argument('-q', help=argparse.SUPPRESS)  # suppress non-error messages during configuration testing
    parser.add_argument('-s', help=argparse.SUPPRESS)  # send signal to a master process: stop, quit, reopen, reload
    # parser.add_argument('-p', help=argparse.SUPPRESS)  # set prefix path (default: /etc/nginx/)
    parser.add_argument('-c', help=argparse.SUPPRESS)  # set configuration file (default: /etc/nginx/nginx.conf)
    parser.add_argument('-g', help=argparse.SUPPRESS)  # set global directives out of configuration file

    # Craziness
    parser.add_argument('-{', help='Starting parentheses (raise hierarchy). Note: `-b`/`--block` does this also.',
                        dest='open_paren', nargs='*')
    parser.add_argument('-}', help='Ending parentheses (lower hierarchy)', dest='close_paren', nargs='*')

    return parser


has_call = lambda attr, target: hasattr(target, attr) and hasattr(getattr(target, attr), '__call__')


def add_to(target, item):
    _has_call = partial(has_call, target=target)

    if _has_call('append'):
        target = target  # type: list
        target.append(item)
    elif _has_call('add'):
        target = target  # type: set
        target.add(item)
    elif _has_call('__setitem__'):
        target = target  # type: dict
        arity = len(item)
        if len(item) != 2:
            raise TypeError('expected 2 arguments, got {} from {!r}'.format(arity, item))
        target.__setitem__(*item)
    elif _has_call('join'):
        target = target  # type: bytes
        return target.join(item)
    else:
        raise NotImplementedError('Adding to {!r}'.format(type(target)))

    return target


def process_group(group, paired_sequence_handler):
    processed_group = []

    if len(group) == 0:
        return processed_group

    odd = (len(group) % 2) != 0
    raw_pairs = group[:-1] if odd else group
    pairs = toolz.partition_all(2, raw_pairs)
    result = paired_sequence_handler(pairs)

    if result:
        processed_group.append(result)

    if odd:
        processed_group.append(group[-1])

    return processed_group


def build_dict_by_update(sequence, pair_handler):
    # return dict(pair_handler(*pair)
    #             for pair in sequence)
    result = {}
    for pair in sequence:
        result.update(pair_handler(*pair))

    return result


def build_list_by_update(sequence, pair_handler):
    # return dict(pair_handler(*pair)
    #             for pair in sequence)
    result = []
    for pair in sequence:
        result.append(pair_handler(*pair))

    return result


def solution(source, group_handler):
    built = []
    group = []

    sentinel = object()

    for value in itertools.chain(source, [sentinel]):
        if not isinstance(value, list) and value is not sentinel:
            group.append(value)
            continue

        built.extend(group_handler(group))
        group = []

        if value is sentinel:
            break

        result = solution(
            source=value,
            group_handler=group_handler,
        )
        built.append(result)

    return built


parse_to_directives = partial(
    solution,
    group_handler=partial(
        process_group,
        paired_sequence_handler=lambda s_: build_list_by_update(
            s_,
            lambda key, value: (lambda k, v: {
                'args': [v],
                'directive': k.lstrip('-'),
                'line': None
            })(*((key, value) if key.startswith('-') else (value, key)))
        )
    )
)


def make_directive(args=None, directive=None, block=None, line=None, level=None):
    return {
        'args': args or [],
        'directive': directive or None,
        'block': block or [],
        'line': line or None,
        '_level': level or 0
    }


def make_update_directive(maybe_directive, **kwargs):
    if maybe_directive is None or len(maybe_directive) == 0:
        return make_directive(**kwargs)

    for k, v in kwargs.items():
        if not maybe_directive[k]:
            maybe_directive[k] = v
        else:
            add_to(maybe_directive[k], v)

    return maybe_directive


def traverse_to_level(directive, level):
    if directive['_level'] == level:
        return directive

    for _directive in directive['block']:
        found = traverse_to_level(_directive, level)
        if found is not None:
            return found

    return None


def set_directive(top_directive, option, level):
    directive = traverse_to_level(top_directive, level)
    if directive is None:
        directive = traverse_to_level(top_directive, level - 1)
    assert directive is not None
    if option.startswith('-'):
        if directive['directive'] is None:
            directive['directive'] = option
        elif directive['_level'] < level:
            directive['block'].append(make_directive(option))
        else:
            directive = traverse_to_level(top_directive, level -1)
            directive['block'].append(make_directive(option))
            raise NotImplementedError()
    else:
        directive['args'].append(option)

    return directive


def main(argv=None):
    parser = _build_parser()
    supported_destinations_f = lambda: frozenset(action.dest
                                                 for action in parser._actions
                                                 if isinstance(action, argparse._StoreAction))
    supported_fields_f = lambda: frozenset(option_string
                                           for action in parser._actions
                                           for option_string in action.option_strings)

    # supported_fields = supported_fields_f()
    level, top_d, last_block = 0, make_directive(), None
    sen_d = top_d
    for idx, arg in enumerate(argv or sys.argv[1:]):
        if arg == '-{':
            level += 1
            sen_d = traverse_to_level(top_d, level)
        elif arg in frozenset(('-b', '--block')):
            level += 1
            last_block = idx
        elif arg == '-}':
            level -= 1
        elif idx == last_block - 1:
            if sen_d['directive'] is None:
                sen_d['directive'] = arg
            else:
                raise NotImplementedError()
        elif idx == last_block - 2:
            if len(sen_d['args']) == 0:
                sen_d['args'].append(arg)
            else:
                raise NotImplementedError()
        else:
            directive = set_directive(top_d, arg, level)
            assert directive is not None
            sen_d = directive

    return top_d
    """
    level, working, whole, view, last_block = 0, [], [], None, None
    # print('idx\tlevel\targ')
    for idx, arg in enumerate(argv or sys.argv[1:]):
        # print(idx, '\t', level, '\t\t\'', arg, '\'', sep='')
        if arg == '-{':
            level += 1
        elif arg in frozenset(('-b', '--block')):
            level += 1
            view = working
            '''
            for i in range(level - 1):
                view = view[-1]
            '''
            view.append([make_directive(level=level)])
            last_block = idx
            view = view[-1]
        elif arg == '-}' and level == 0:
            whole.append(tuple(working))
            working.clear()
            level -= 1
        elif last_block == idx - 1:
            add_update_support_cli_args(arg, parser, supported_fields_f)

            if view[-1]['directive'] is None:
                view[-1]['directive'] = arg
            else:
                raise NotImplementedError()
                # view[-1]['block'].append(make_directive(directive=arg))
                # view = view[-1]['block']
        else:
            if arg.startswith('-'):
                add_update_support_cli_args(arg, parser, supported_fields_f)

                directive = arg.lstrip('-')
                if isinstance(view, (list, tuple)) and len(view) == 0:
                    view.append(make_directive(directive=directive, level=level))
                    view = view[-1]['block']
                elif view[-1]['directive'] is None:
                    view[-1]['directive'] = directive
                else:  # if last_block == idx - 2:
                    # print("{}\n\t['block'].append(make_directive(directive={!r}))".format(view[-1], directive))
                    if level == view[-1]['_level']:
                        view.append(make_directive(directive=directive, level=level))
                    else:
                        view[-1]['block'].append(make_directive(directive=directive, level=level))
                    view = view[-1]['block']
                # else:
                #    view.append(make_directive(directive=directive))
            else:
                print('view:', view, ';')
                if isinstance(view, (list, tuple)) and len(view) == 0:
                    view.append(make_directive(args=[arg], level=level))
                    view = view[-1]['block']
                elif len(view[-1]['args']) == 0:
                    view[-1]['args'].append(arg)
                elif view[-1]['_level'] == level:
                    view.append(make_directive(args=[arg]))
                    view = view[-1]['block']
                elif level > view[-1]['_level']:
                    view[-1]['block'].append(make_directive(args=[arg]))
                    view = view[-1]['block']
                else:
                    print("view[-1]:", view[-1])
                    raise NotImplementedError()
                    #
                    #

    if level & 1 != 0:
        raise argparse.ArgumentTypeError('Imbalanced {}')

    # return whole
    return remap(tuple((e
                        for elements in whole
                        for elem in elements
                        for e in elem)),
                 visit=lambda p, k, v: v != [] and k != '_level')
    """


def add_update_support_cli_args(arg, parser, supported_fields_f):
    supported_fields = supported_fields_f()
    dest = unquoted_str(arg).lstrip('-')
    if arg.startswith('-') and arg not in supported_fields:
        parser.add_argument(
            arg, type=unquoted_str, help='Autogenerated',
            dest='{}_autogenerated'.format(dest)
        )
    return supported_fields_f()


if __name__ == '__main__':
    r = main()
    print('main')
    pp(r)
    # Popen([which('bash'), '-c', "while true; do echo 'foo'; sleep 2s; done"])

if __name__ == '__main__2':
    nginx, ctl = {}, {}
    it_consumes(nginx.update({k: v}) if k in frozenset(('?', 'V', 't', 'T', 'q', 's', 'c', 'g'))
                else ctl.update({k: v})
                for k, v in vars(_build_parser().parse_args()).items())
    pp(ctl)

    # pp({'nginx': nginx, 'ctl': ctl})

__all__ = ['_build_parser', 'main']
