# -*- coding: utf-8 -*-

from ast import parse
from distutils.sysconfig import get_python_lib
from functools import partial
from os import path, listdir
from setuptools import setup, find_packages
from sys import version

if version[0] == "2":
    from itertools import imap as map, ifilter as filter


if __name__ == "__main__":
    package_name = "nginxctl"

    with open(path.join(package_name, "__init__.py")) as f:
        __author__, __version__ = map(
            lambda buf: next(map(lambda e: e.value.s, parse(buf).body)),
            filter(
                lambda line: line.startswith("__version__")
                or line.startswith("__author__"),
                f,
            ),
        )

    to_funcs = lambda *paths: (
        partial(path.join, path.dirname(__file__), package_name, *paths),
        partial(path.join, get_python_lib(prefix=""), package_name, *paths),
    )
    _data_join, _data_install_dir = to_funcs("_data")
    _config_join, _config_install_dir = to_funcs("_config")

    setup(
        name=package_name,
        author=__author__,
        version=__version__,
        install_requires=["pyyaml"],
        test_suite=package_name + ".tests",
        packages=find_packages(),
        package_dir={"package_name": package_name},
        data_files=[
            (_data_install_dir(), list(map(_data_join, listdir(_data_join())))),
            (_config_install_dir(), list(map(_config_join, listdir(_config_join())))),
        ],
    )
