# -*- coding: utf-8 -*-

import ast
import csv
import inspect
from os import listdir, path
from sys import version_info

import pkg_resources

if version_info.major == 2:

    class suppress:
        """
        https://stackoverflow.com/a/34113126
        """

        def __init__(self, *exception):
            self.exceptions = exception

        def __enter__(self):
            pass

        def __exit__(self, exc_type, exc_value, traceback):
            return any(
                isinstance(exc_value, exception) for exception in self.exceptions
            )

    FileNotFoundError = OSError  # noqa: E303
else:
    from contextlib import suppress


class PythonPackageInfo(object):
    @staticmethod
    def get_first_setup_py(cur_dir):
        if "setup.py" in listdir(cur_dir):
            return path.join(cur_dir, "setup.py")
        prev_dir = cur_dir
        cur_dir = path.realpath(path.dirname(cur_dir))
        if prev_dir == cur_dir:
            raise StopIteration()
        return PythonPackageInfo.get_first_setup_py(cur_dir)

    @staticmethod
    def parse_package_name_from_setup_py(setup_py_file_name):
        with open(setup_py_file_name, "rt") as f:
            parsed_setup_py = ast.parse(f.read(), "setup.py")

        return next(
            node.value.s if isinstance(node.value, ast.Str) else node.value.value
            for node in ast.walk(parsed_setup_py)
            if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "package_name"
        )

    # Originally https://stackoverflow.com/a/56032725
    def get_app_name(self):
        # if version_info.major == 2:
        #     return 'nginxctl'  # TODO: Fix this for Python 2.7… or just drop support for that old version

        # Iterate through all installed packages and try to find one that has the app's file in it
        app_def_path = inspect.getfile(self.__class__)
        project_name = None
        with suppress(FileNotFoundError, KeyError, IOError):
            project_name = next(
                (
                    dist.project_name
                    for dist in pkg_resources.working_set
                    if any(
                        app_def_path == path.normpath(path.join(dist.location, r[0]))
                        for r in csv.reader(dist.get_metadata_lines("RECORD"))
                    )
                ),
                None,
            )

        return project_name or self.parse_package_name_from_setup_py(
            self.get_first_setup_py(path.dirname(__file__))
        )


if __name__ == "__main__":
    print(
        "PythonPackageInfo().get_app_name():", PythonPackageInfo().get_app_name(), ";"
    )

__all__ = ["PythonPackageInfo"]
