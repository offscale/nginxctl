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
from boltons.iterutils import get_path, pairwise

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


def main():
    parser = _build_parser()
    # supported_destinations_f = lambda: frozenset(action.dest
    #                                              for action in parser._actions
    #                                              if isinstance(action, argparse._StoreAction))
    supported_fields_f = lambda: frozenset(option_string
                                           for action in parser._actions
                                           for option_string in action.option_strings)

    supported_fields = supported_fields_f()

    level, working, whole, view, last_block = 0, [], [], None, None
    for idx, arg in enumerate(sys.argv[1:]):
        if arg == '-{':
            level += 1
        elif arg in frozenset(('-b', '--block')):
            level += 1
            view = working
            for i in range(level - 1):
                view = view[-1]
            view.append([
                # arg
            ])
            last_block = idx
            view = view[-1]
        elif arg == '-}':
            whole.append(tuple(working))
            print('working:', working, ';')
            working.clear()
            level -= 1
        else:
            # Assume this is part of config grammar not our mistype
            if arg not in supported_fields:
                if arg.startswith('-'):
                    # print('Adding {!r} to {!r}'.format(arg,
                    #                                    supported_fields))
                    fst, _, val = arg.partition(' ')
                    if not val:
                        idx = arg.find('=')
                        if idx > -1:
                            fst, val = arg[idx:], arg[idx:]
                    parser.add_argument(
                        fst, type=unquoted_str, help='Autogenerated',
                        dest=(lambda s: s[2:] if s[1] == '-' else s[1:])(unquoted_str(arg))
                    )
                    supported_fields = supported_fields_f()
            view.append(arg)
    print('whole')
    pp(whole)

    if level & 1 != 0:
        raise argparse.ArgumentTypeError('Imbalanced {}')

    return tuple(map(lambda source: solution(
        source=source,
        group_handler=partial(
            process_group,
            paired_sequence_handler=lambda s_: build_list_by_update(
                s_,
                lambda key, value: (lambda k, v: {'directive': k.replace('-', ''),
                                                  'args': [v]})(
                    *((key, value) if key.startswith('-') else (value, key)))
            )
        ),
    ), whole))

    # remap(whole, visit=get_visitor(whole, last_l))
    # return last_l

    # return tuple(item if isinstance(item, (tuple, list))
    #              else dict(pairwise(item))
    #              for item in whole)


def get_visitor(root, last_l):
    def visit(p, k, v):
        pp({'p': p, 'k': k, 'v': v})
        if len(v) > 1 or len(v) == 1 and v[0] != {}:
            print('last_l:', visit.last_l, ';')
            visit.last_l.clear()
            visit.last_l += v

        if len(p) > 0:
            gp = get_path(root, p)
            print('gp:', gp, ';')
            return k, dict(pairwise(gp))
            # print('get_path:', dict(pairwise(gp)), ';')
        return k, v

    visit.last_l = last_l

    return visit


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
