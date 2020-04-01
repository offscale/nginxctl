#!/usr/bin/env python

import argparse
import os
import sys
from argparse import ArgumentParser
from enum import Enum
from functools import partial
from itertools import chain
from shutil import which, copy
from subprocess import Popen
from tempfile import mkdtemp

import crossplane
from pkg_resources import resource_filename

from nginxctl import __version__, get_logger
from nginxctl.helpers import it_consumes, pp, strings, unquoted_str
from nginxctl.parser import parse_cli_config
from nginxctl.pkg_utils import PythonPackageInfo

logger = get_logger(sys.modules[__name__].__name__)


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
    parser.add_argument('command', help='serve, emit, or dry_run', type=Command, choices=list(Command))

    parser.add_argument('--version', action='version', version='%(prog)s {}'.format(__version__))

    # parser.add_argument('--dns', help='DNS alias')
    # parser.add_argument('--ip', help='Public IP address', required=True)
    parser.add_argument('--listen', help='Listen (e.g., port)', default='8080', nargs='*')
    parser.add_argument('--prefix', help='set prefix path, e.g., {!r}'.format(default_prefix),
                        default=default_prefix)
    parser.add_argument('--root', help=argparse.SUPPRESS, nargs='*',
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


if __name__ == '__main__':
    omit, nginx, parser = _build_parser()
    known, unknown = parser.parse_known_args()
    pp({k: v
        for k, v in known._get_kwargs()
        if k not in omit | nginx})

    config = parse_cli_config(sys.argv[2:])
    parsed_config_str = crossplane.build([config]) + os.linesep

    if known.command.value == 'serve':
        temp_dir = mkdtemp('_nginxctl', 'nginxctl_')
        logger.debug('temp_dir:\t{!r}'.format(temp_dir))

        _config_files = 'nginx.conf', 'mime.types'

        nginx_conf_join = partial(os.path.join, os.path.join(
            os.path.dirname(os.path.join(resource_filename(PythonPackageInfo().get_app_name(), '__init__.py'))),
            '_config'
        ))
        config_files = tuple(map(nginx_conf_join, _config_files))
        it_consumes(map(partial(copy, dst=temp_dir), config_files))
        sites_available = os.path.join(temp_dir, 'sites-available')
        os.mkdir(sites_available)
        server_conf = os.path.join(sites_available, 'server.conf')
        with open(server_conf, 'wt') as f:
            f.write(parsed_config_str)

        # Include this config in the new nginx.conf
        nginx_conf = os.path.join(temp_dir, _config_files[0])
        nginx_conf_parsed = crossplane.parse(nginx_conf, catch_errors=False, comments=False)
        nginx_conf_parse = next(config
                                for config in nginx_conf_parsed['config']
                                if os.path.basename(config['file']) == 'nginx.conf')
        nginx_conf_parse['parsed'][-1]['block'].append({
            'args': [os.path.join(sites_available, '*.conf')],
            'directive': 'include',
            'includes': [2],
            'line': nginx_conf_parse['parsed'][-1]['line'] + 2
        })
        # print('nginx_conf_parse:', nginx_conf_parse, ';')
        config_str = crossplane.build(nginx_conf_parse['parsed'])

        os.remove(nginx_conf)
        with open(nginx_conf, 'wt') as f:
            f.write(config_str + os.linesep)

        Popen([known.nginx,
               '-c', config_files[0]] + list(chain.from_iterable(('-{}'.format(k), v)
                                                                 for k, v in known._get_kwargs()
                                                                 if k in nginx and v and k != 'c')))
        # os.remove(server_conf)
        # os.rmdir(sites_available)
        # it_consumes(os.remove, config_files)
        # os.rmdir(temp_dir)
    else:
        raise NotImplementedError(known.command)

__all__ = ['_build_parser']
