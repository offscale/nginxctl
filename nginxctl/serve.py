from __future__ import print_function

import os
from collections import deque
from functools import partial
from itertools import count
from shutil import copy
from subprocess import Popen
from sys import modules

import crossplane
from boltons.iterutils import research
from pkg_resources import resource_filename

from nginxctl import get_logger
from nginxctl.helpers import is_directive, pp
from nginxctl.pkg_utils import PythonPackageInfo

logger = get_logger(
    ":".join((PythonPackageInfo().get_app_name(), modules[__name__].__name__))
)


def serve(
    known,
    nginx_command,
    parsed_config,
    parsed_config_str,
    parsed_config_http,
    parsed_config_http_str,
):
    if not os.path.isdir(known.temp_dir):
        os.mkdir(known.temp_dir)
    logger.debug("temp_dir:\t{!r}".format(known.temp_dir))
    _config_files = "nginx.conf", "mime.types"
    nginx_conf_join = partial(
        os.path.join,
        os.path.join(
            os.path.dirname(
                os.path.join(
                    resource_filename(PythonPackageInfo().get_app_name(), "__init__.py")
                )
            ),
            "_config",
        ),
    )
    config_files = tuple(map(nginx_conf_join, _config_files))
    deque(map(partial(copy, dst=known.temp_dir), config_files), maxlen=0)
    sites_available = os.path.join(known.temp_dir, "sites-available")
    if not os.path.isdir(sites_available):
        os.mkdir(sites_available)
    server_conf = os.path.join(sites_available, "server.conf")
    if parsed_config is not None:
        pp(parsed_config)
        pp(
            research(
                parsed_config,
                query=lambda p, k, v: is_directive(v)
                and print("k:", k, ";\nv:", v, ";"),
            )
        )
    # pp(research(parsed_config, query=lambda p, k, v: is_directive(v)))
    with open(server_conf, "wt") as f:
        if parsed_config_http_str is not None:
            f.write(parsed_config_http_str)
        if parsed_config_str is not None:
            f.write(parsed_config_str)
    # Include this config in the new nginx.conf
    nginx_conf = os.path.join(known.temp_dir, _config_files[0])
    nginx_conf_parsed = crossplane.parse(nginx_conf, catch_errors=False, comments=False)
    nginx_conf_parse = next(
        config
        for config in nginx_conf_parsed["config"]
        if os.path.basename(config["file"]) == "nginx.conf"
    )

    line = count(nginx_conf_parse["parsed"][-1]["block"][-1]["line"])
    del nginx_conf_parse["parsed"][-1]["block"][-1]
    nginx_conf_parse["parsed"].insert(1, {"args": ["off"], "directive": "daemon"})
    nginx_conf_parse["parsed"][-1]["block"] += [
        {"args": ["stderr", "warn"], "directive": "error_log", "line": next(line)},
        {"args": ["/dev/stdout"], "directive": "access_log", "line": next(line)},
        {
            "args": [os.path.join(sites_available, "*.conf")],
            "directive": "include",
            "includes": [2],
            "line": next(line),
        },
    ]
    config_str = crossplane.build(nginx_conf_parse["parsed"])
    os.remove(nginx_conf)
    with open(nginx_conf, "wt") as f:
        f.write(config_str + os.linesep)
    # logger.error
    print(
        "nginx is running. Stop with: {}".format(
            " ".join((known.nginx, "-c", nginx_conf, "-s", "stop"))
        )
    )
    Popen([known.nginx, "-c", nginx_conf] + nginx_command)
    # os.remove(server_conf)
    # os.rmdir(sites_available)
    # deque(os.remove, config_files)
    # os.rmdir(temp_dir)
