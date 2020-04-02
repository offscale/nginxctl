#!/usr/bin/env python

import argparse
import os
import sys
from argparse import ArgumentParser
from enum import Enum
from itertools import chain
from operator import itemgetter
from shutil import which
from subprocess import Popen

import crossplane

from nginxctl import __version__, get_logger
from nginxctl.helpers import it_consumes, pp, strings, unquoted_str, gettemp
from nginxctl.parser import parse_cli_config
from nginxctl.pkg_utils import PythonPackageInfo
from nginxctl.serve import serve

logger = get_logger(sys.modules[__name__].__name__)


class Command(Enum):
    serve = 'serve'
    emit = 'emit'
    dry_run = 'dry_run'
    nginx = 'nginx'

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


def _build_parser():
    if 'GITHUB_ACTION' in os.environ:
        default_nginx, default_prefix, default_conf = (
            '/usr/local/bin/nginx', '/etc/nginx/', '/etc/nginx/nginx.conf'
        )
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
    parser.add_argument('command', help='serve, emit, nginx, or dry_run', type=Command, choices=list(Command))

    parser.add_argument('--version', action='version', version='%(prog)s {}'.format(__version__))

    # parser.add_argument('--dns', help='DNS alias')
    # parser.add_argument('--ip', help='Public IP address', required=True)
    parser.add_argument('--listen', help='Listen (e.g., port)', default='8080', nargs='*')
    parser.add_argument('--prefix', help='set prefix path, e.g., {!r}'.format(default_prefix),
                        default=default_prefix)
    parser.add_argument('--root', help=argparse.SUPPRESS, nargs='*',
                        type=unquoted_str, action=ReadableDir, default=os.getcwd())
    parser.add_argument('--temp_dir', help='serve uses this directory',
                        dest='temp_dir', default=gettemp('_nginxctl', 'nginxctl_'))
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
    parser.add_argument('-c', '--config',
                        help='Name of file. Placed in prefix folder—e.g., {!r}—if not absolute.'
                             ' E.g., nginx.conf'.format(default_nginx),
                        default=default_conf)  # set configuration file (default: /etc/nginx/nginx.conf)
    parser.add_argument('-g', help=argparse.SUPPRESS)  # set global directives out of configuration file

    # Craziness
    parser.add_argument('-{', help='Starting parentheses (raise hierarchy). Note: `-b`/`--block` does this also.',
                        dest='open_paren', nargs='*')
    parser.add_argument('-}', help='Ending parentheses (lower hierarchy)', dest='close_paren', nargs='*')

    return frozenset(
        ('listen', 'root', 'block',
         'open_paren', 'close_paren',
         )
    ), frozenset(
        ('?', 'T', 'V', 't',
         'T', 'q', 's',  # 'c',
         'g')
    ), parser


def add_update_support_cli_args(arg, parser, supported_fields_f):
    supported_fields = supported_fields_f()
    dest = unquoted_str(arg).lstrip('-')
    if arg.startswith('-') and arg not in supported_fields:
        parser.add_argument(
            arg, type=unquoted_str, help='Autogenerated',
            dest='{}_autogenerated'.format(dest)
        )
    return supported_fields_f()


def main():
    omit, nginx, parser = _build_parser()
    known, unknown = parser.parse_known_args()
    nginx_command = list(chain.from_iterable(('-{}'.format(k), v)
                                             for k, v in known._get_kwargs()
                                             if k in nginx and v and k != 'c'))
    omit_nginx = omit | nginx
    pp({k: v
        for k, v in known._get_kwargs()
        if k not in omit_nginx})

    if known.command.value != 'nginx':
        fs = frozenset(map(lambda s: '--{}'.format(s),
                           frozenset(map(itemgetter(0), filter(lambda cn: cn[1] is not None,
                                                               known._get_kwargs()))) - omit_nginx))
        parsed_config_str = crossplane.build([parse_cli_config(
            tuple(chain.from_iterable((k, v)
                                      for k, v in zip(*[iter(sys.argv[2:])] * 2)
                                      if k not in fs)) + (
                (sys.argv[-1],) if len(sys.argv[2:]) & 1 == 1 else tuple()))]) + os.linesep
        if known.command.value == 'serve':
            serve(known, nginx_command, parsed_config_str)
        else:
            raise NotImplementedError(known.command)
    else:
        Popen([known.nginx] + nginx_command)


if __name__ == '__main__':
    main()

__all__ = ['_build_parser']
