from __future__ import absolute_import

from functools import partial
from os import path
from unittest import TestCase, main as unittest_main

import crossplane
from pkg_resources import resource_filename

from nginxctl.helpers import filter_map_block, replace_attr, get_dict_by_key_val, del_keys_d
from nginxctl.pkg_utils import PythonPackageInfo


class TestParser(TestCase):
    def setUp(self):
        nginx_conf = path.join(
            path.dirname(path.join(resource_filename(PythonPackageInfo().get_app_name(), '__init__.py'))),
            '_config', 'nginx.conf')
        # self.nginx_conf_lex = tuple(crossplane.lex(nginx_conf))
        self.nginx_conf_parse = crossplane.parse(nginx_conf, catch_errors=False, comments=True)

    def test_filter_map_block(self):
        for config in self.nginx_conf_parse['config']:
            self.assertEqual(config['status'], 'ok')

        nginx_conf_parse = next(config
                                for config in self.nginx_conf_parse['config']
                                if path.basename(config['file']) == 'nginx.conf')

        no_line = partial(del_keys_d, key='line')

        self.assertDictEqual(
            no_line(get_dict_by_key_val(nginx_conf_parse['parsed'].copy(), 'directive', 'server_name')),
            {'directive': 'server_name', 'args': ['localhost']})
        self.assertDictEqual(no_line(get_dict_by_key_val(nginx_conf_parse['parsed'].copy(), 'directive', 'listen')),
                             {'directive': 'listen', 'args': ['80']})

        result = filter_map_block(
            nginx_conf_parse['parsed'],
            ((lambda block: all((isinstance(block, dict),
                                 block.get('directive', '') == 'server_name',
                                 block['args'] == ['localhost']))),
             lambda block: replace_attr(block, 'args', ['example.com'])),
            ((lambda block: all((isinstance(block, dict),
                                 block.get('directive', '') == 'listen',
                                 block['args'] == ['80']))),
             lambda block: replace_attr(block, 'args', ['8080'])),
        )

        self.assertDictEqual(no_line(get_dict_by_key_val(result, 'directive', 'server_name')),
                             {'directive': 'server_name', 'args': ['example.com']})
        self.assertDictEqual(no_line(get_dict_by_key_val(result, 'directive', 'listen')),
                             {'directive': 'listen', 'args': ['8080']})


if __name__ == '__main__':
    unittest_main()
