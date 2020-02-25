import ast
import csv
import inspect
from contextlib import suppress
from os import listdir, path

import pkg_resources


class PythonPackageInfo(object):
    @staticmethod
    def get_first_setup_py(cur_dir):
        if 'setup.py' in listdir(cur_dir):
            return path.join(cur_dir, 'setup.py')
        prev_dir = cur_dir
        cur_dir = path.realpath(path.dirname(cur_dir))
        if prev_dir == cur_dir:
            raise StopIteration()
        return PythonPackageInfo.get_first_setup_py(cur_dir)

    @staticmethod
    def parse_package_name_from_setup_py(setup_py_file_name):
        with open(setup_py_file_name, 'rt') as f:
            parsed_setup_py = ast.parse(f.read(), 'setup.py')

        # Assumes you have an `if __name__ == '__main__':`, and that it's at the end:
        main_body = next(sym for sym in parsed_setup_py.body[::-1]
                         if isinstance(sym, ast.If)).body

        setup_call = next(sym.value
                          for sym in main_body[::-1]
                          if isinstance(sym, ast.Expr)
                          and isinstance(sym.value, ast.Call)
                          and sym.value.func.id in frozenset(('setup',
                                                              'distutils.core.setup',
                                                              'setuptools.setup')))

        package_name = next(keyword
                            for keyword in setup_call.keywords
                            if keyword.arg == 'name' and isinstance(keyword.value, ast.Name))

        # Return the raw string if it is one
        if isinstance(package_name.value, ast.Str):
            return package_name.s

        # Otherwise it's a variable at the top of the `if __name__ == '__main__'` block
        elif isinstance(package_name.value, ast.Name):
            return next(sym.value.s
                        for sym in main_body
                        if isinstance(sym, ast.Assign)
                        and isinstance(sym.value, ast.Str)
                        and any(target.id == package_name.value.id
                                for target in sym.targets)
                        )

        else:
            raise NotImplemented('Package name extraction only built for raw strings and '
                                 'variables in the same function that setup() is called')

    # Originally https://stackoverflow.com/a/56032725
    def get_app_name(self) -> str:
        # Iterate through all installed packages and try to find one that has the app's file in it
        app_def_path = inspect.getfile(self.__class__)
        with suppress(FileNotFoundError):
            return next((dist.project_name
                         for dist in pkg_resources.working_set
                         if any(app_def_path == path.normpath(path.join(dist.location, r[0]))
                                for r in csv.reader(dist.get_metadata_lines('RECORD')))),
                        None) or self.parse_package_name_from_setup_py(self.get_first_setup_py(path.dirname(__file__)))


if __name__ == '__main__':
    print('PythonPackageInfo().get_app_name():', PythonPackageInfo().get_app_name(), ';')

__all__ = ['PythonPackageInfo']
