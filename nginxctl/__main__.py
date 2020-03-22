#!/usr/bin/env python

import argparse
import os
import sys
from argparse import ArgumentParser
from enum import Enum
from functools import reduce
from shutil import which

from boltons.iterutils import remap

from nginxctl import __version__
from nginxctl.helpers import it_consumes, pp, strings
from nginxctl.pkg_utils import PythonPackageInfo


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
        prog='python -m {}'.format(PythonPackageInfo().get_app_name()),
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


def main(argv=None):
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
