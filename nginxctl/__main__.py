#!/usr/bin/env python

from argparse import ArgumentParser

from nginxctl import __version__


def _build_parser():
    parser = ArgumentParser(
        prog='python -m nginxctl',
        description='Register node to cluster(s). Node is found by manual specification, or popped from a queue.',
        epilog='Example usage: %(prog)s -q etcd -r mesos:location -r etcd:location -r consul:location'
    )
    parser.add_argument('-obj', '--dns', help='DNS alias')
    parser.add_argument('-i', '--ip', help='Public IP address')
    parser.add_argument('-p', '--port', help='Port', type=int)
    parser.add_argument('-n', '--nginx', help='Path to nginx binary, defaults to first in PATH')
    parser.add_argument('-s', help='send signal to a master process: stop, quit, reopen, reload', dest='signal')
    parser.add_argument('--version', action='version', version='%(prog)s {}'.format(__version__))
    return parser


if __name__ == '__main__':
    args = _build_parser().parse_args()
    print(args)
