from __future__ import absolute_import, unicode_literals

import unittest
from copy import deepcopy
from functools import partial
from os import linesep, path
from shutil import rmtree
from tempfile import mkdtemp
from unittest import TestCase
from unittest import main as unittest_main

import crossplane
from boltons.iterutils import remap
from pkg_resources import resource_filename

from nginxctl.helpers import del_keys_d, get_dict_by_key_val, update_directive, pp
from nginxctl.parser import parse_cli_config
from nginxctl.pkg_utils import PythonPackageInfo


class TestParser(TestCase):
    maxDiff = 1200

    def setUp(self):
        app_name = PythonPackageInfo().get_app_name()

        assert app_name is not None
        self.nginx_conf_join = partial(
            path.join,
            path.join(
                path.dirname(path.join(resource_filename(app_name, "__init__.py"))),
                "_config",
            ),
        )
        self.nginx_conf_fname = self.nginx_conf_join("nginx.conf")
        self.server_conf_fname = self.nginx_conf_join("server.conf")
        # self.nginx_conf_lex = tuple(crossplane.lex(nginx_conf))
        self.nginx_conf_parse = crossplane.parse(
            self.nginx_conf_fname, catch_errors=False, comments=False
        )

        self.temp_dir = mkdtemp(app_name, self.__class__.__name__)
        self.tmp_nginx_conf_fname = path.join(self.temp_dir, "nginx.conf")

    def tearDown(self):
        rmtree(self.temp_dir)

    @unittest.skip
    def test_filter_map_block(self):
        pp(self.nginx_conf_parse)
        for config in self.nginx_conf_parse["config"]:
            self.assertEqual(config["status"], "ok")

        nginx_conf_parse = next(
            config
            for config in self.nginx_conf_parse["config"]
            if path.basename(config["file"]) == "nginx.conf"
        )

        no_line = partial(del_keys_d, key="line")

        self.assertDictEqual(
            no_line(
                get_dict_by_key_val(
                    deepcopy(nginx_conf_parse["parsed"]), "directive", "server_name"
                )
            ),
            {"directive": "server_name", "args": ["localhost"]},
        )
        self.assertDictEqual(
            no_line(
                get_dict_by_key_val(
                    deepcopy(nginx_conf_parse["parsed"]), "directive", "listen"
                )
            ),
            {"directive": "listen", "args": ["80"]},
        )

        nginx_conf_parse["parsed"] = remap(
            nginx_conf_parse["parsed"],
            visit=update_directive(
                "server_name", ["localhost"], new_args=["example.com"]
            ),
        )
        nginx_conf_parse["parsed"] = remap(
            nginx_conf_parse["parsed"],
            visit=update_directive("listen", ["80"], new_args=["8080"]),
        )
        # pp(nginx_conf_parse['parsed'])
        # print(crossplane.build(self.nginx_conf_parse['config'][0]['parsed']))
        self.assertDictEqual(
            no_line(
                get_dict_by_key_val(
                    nginx_conf_parse["parsed"], "directive", "server_name"
                )
            ),
            {"directive": "server_name", "args": ["example.com"]},
        )
        self.assertDictEqual(
            no_line(
                get_dict_by_key_val(nginx_conf_parse["parsed"], "directive", "listen")
            ),
            {"directive": "listen", "args": ["8080"]},
        )

    def test_add_include_directive(self):
        if path.isfile(self.tmp_nginx_conf_fname):
            return  # Early exit, don't worry about race conditions, it'll just overwrite
        nginx_conf_parse = next(
            config
            for config in self.nginx_conf_parse["config"]
            if path.basename(config["file"]) == "nginx.conf"
        )
        nginx_conf_parse["parsed"] = remap(
            nginx_conf_parse["parsed"],
            visit=update_directive(
                "server_name", ["localhost"], new_args=["example.com"]
            ),
        )
        nginx_conf_parse["parsed"][-1]["block"].append(
            {
                "args": [self.server_conf_fname],
                "directive": "include",
                "includes": [2],
                "line": 116,
            }
        )
        # print('nginx_conf_parse:', nginx_conf_parse, ';')
        config_str = crossplane.build(nginx_conf_parse["parsed"])
        self.assertEqual(
            config_str.split("\n")[-2].lstrip(),
            "include {};".format(self.server_conf_fname),
        )
        with open(self.tmp_nginx_conf_fname, "wt") as f:
            f.write(config_str)

    def test_cli_args(self):
        output = parse_cli_config(
            [
                "-b",
                "server",
                "--server_name",
                "localhost",
                "--listen",
                "8080",
                "-b",
                "location",
                "/",
                "--root",
                "'/tmp/wwwroot'",
                "-}",
                "-}",
            ]
        )
        self.assertDictEqual(
            output,
            {
                "args": [],
                "block": [
                    {
                        "args": ["localhost"],
                        "block": None,
                        "directive": "server_name",
                        "line": 2,
                    },
                    {"args": ["8080"], "block": None, "directive": "listen", "line": 3},
                    {
                        "args": ["/"],
                        "block": [
                            {
                                "args": ["'/tmp/wwwroot'"],
                                "block": None,
                                "directive": "root",
                                "line": 6,
                            }
                        ],
                        "directive": "location",
                        "line": 5,
                    },
                ],
                "directive": "server",
                "line": 1,
            },
        )

    def test_emit_config(self):
        output = parse_cli_config(
            [
                "-b",
                "server",
                "--server_name",
                "localhost",
                "--listen",
                "8080",
                "-b",
                "location",
                "/",
                "--root",
                "/tmp/wwwroot",
                "-}",
                "-}",
            ]
        )
        with open(self.nginx_conf_join("server.conf")) as f:
            server_conf = f.read()
        self.assertEqual(server_conf, crossplane.build([output]) + linesep)


if __name__ == "__main__":
    unittest_main()
