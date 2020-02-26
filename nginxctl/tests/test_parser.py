from __future__ import absolute_import

from copy import deepcopy
from functools import partial
from os import path
from shutil import rmtree
from tempfile import mkdtemp
from unittest import TestCase, main as unittest_main

import crossplane
from boltons.iterutils import remap
from pkg_resources import resource_filename

from nginxctl.helpers import get_dict_by_key_val, del_keys_d, update_directive
from nginxctl.pkg_utils import PythonPackageInfo


class TestParser(TestCase):
    def setUp(self):
        app_name = PythonPackageInfo().get_app_name()
        self.nginx_conf_fname = path.join(
            path.dirname(path.join(resource_filename(app_name, '__init__.py'))),
            '_config', 'nginx.conf')
        # self.nginx_conf_lex = tuple(crossplane.lex(nginx_conf))
        self.nginx_conf_parse = crossplane.parse(self.nginx_conf_fname, catch_errors=False, comments=False)

        self.temp_dir = mkdtemp(app_name, self.__class__.__name__)

    def tearDown(self):
        rmtree(self.temp_dir)

    def test_filter_map_block(self):
        for config in self.nginx_conf_parse['config']:
            self.assertEqual(config['status'], 'ok')

        nginx_conf_parse = next(config
                                for config in self.nginx_conf_parse['config']
                                if path.basename(config['file']) == 'nginx.conf')

        no_line = partial(del_keys_d, key='line')

        self.assertDictEqual(
            no_line(get_dict_by_key_val(deepcopy(nginx_conf_parse['parsed']), 'directive', 'server_name')),
            {'directive': 'server_name', 'args': ['localhost']})
        self.assertDictEqual(no_line(get_dict_by_key_val(deepcopy(nginx_conf_parse['parsed']), 'directive', 'listen')),
                             {'directive': 'listen', 'args': ['80']})

        nginx_conf_parse['parsed'] = remap(
            nginx_conf_parse['parsed'],
            visit=update_directive('server_name', ['localhost'], new_args=['example.com'])
        )
        nginx_conf_parse['parsed'] = remap(
            nginx_conf_parse['parsed'],
            visit=update_directive('listen', ['80'], new_args=['8080'])
        )
        # print(crossplane.build(self.nginx_conf_parse['config'][0]['parsed']))
        self.assertDictEqual(no_line(get_dict_by_key_val(nginx_conf_parse['parsed'], 'directive', 'server_name')),
                             {'directive': 'server_name', 'args': ['example.com']})
        self.assertDictEqual(no_line(get_dict_by_key_val(nginx_conf_parse['parsed'], 'directive', 'listen')),
                             {'directive': 'listen', 'args': ['8080']})


if __name__ == '__main__':
    unittest_main()
