nginxctl
========
[![License](https://img.shields.io/badge/license-Apache--2.0%20OR%20MIT%20OR%20CC0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
![Python version range](https://img.shields.io/badge/python-2.7%20|%203.5%20|%203.6%20|%203.7%20|%203.8%20|%203.9%20|%203.10%20|%203.11%20|%203.12%20|%203.13-blue.svg)
![Python lint & test](https://github.com/offscale/nginxctl/workflows/Python%20lint%20&%20test/badge.svg)
[![black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)

Commands for modifying and controlling nginx over the command-line.

## Install dependencies

    python -m pip install -r requirements.txt

## Install package

    python -m pip install .

## Usage

    usage: python -m nginxctl [-h] [--version] [--listen [LISTEN ...]]
                              [--prefix PREFIX] [--temp_dir TEMP_DIR]
                              [--nginx NGINX] [-b [BLOCK ...]] [-c CONFIG]
                              [-{ [OPEN_PAREN ...]] [-} [CLOSE_PAREN ...]]
                              {dry_run,emit,nginx,serve,upsert}
    
    Commands for modifying and controlling nginx over the command-line.
    
    positional arguments:
      {dry_run,emit,nginx,serve,upsert}
                            serve, emit, nginx, or dry_run
    
    options:
      -h, --help            show this help message and exit
      --version             show program's version number and exit
      --listen [LISTEN ...]
                            Listen (e.g., port)
      --prefix PREFIX       set prefix path, e.g., '/opt/homebrew/etc/nginx'
      --temp_dir TEMP_DIR   serve uses this directory
      --nginx NGINX         Path to nginx binary, defaults to first in PATH, i.e.,
                            '/opt/homebrew/bin/nginx'
      -b [BLOCK ...], --block [BLOCK ...]
                            Block, e.g., server or http
      -c CONFIG, --config CONFIG
                            Name of file. Placed in prefix folder—e.g.,
                            '/opt/homebrew/bin/nginx'—if not absolute. E.g.,
                            nginx.conf
      -{ [OPEN_PAREN ...]   Starting parentheses (raise hierarchy). Note:
                            `-b`/`--block` does this also.
      -} [CLOSE_PAREN ...]  Ending parentheses (lower hierarchy)
    
    Example usage: python -m nginxctl -w '/tmp/wwwroot' -p 8080 -i '192.168.2.1'
    -w '/mnt/webroot' -p 9001 -i 'localhost' --path '/api' --proxy-pass
    '192.168.2.1/api'

## Examples

### Serve local directory and then stop server

    $ python -m nginxctl serve --temp_dir '/tmp' \ 
                -b 'server' \
                  --server_name 'localhost' --listen '8080' \
                  -b location '/' \
                    --root '/tmp/wwwroot' \
                  -'}' \
                -'}'
    nginx is running. Stop with: /usr/local/bin/nginx -c /tmp/nginx.conf -s stop
    $ curl -Is http://localhost:8080 | head -n1
    127.0.0.1 - - [03/Apr/2020:01:21:45 +1100] "HEAD / HTTP/1.1" 200 0 "-" "curl/7.64.1"
    HTTP/1.1 200 OK
    $ python -m nginxctl nginx --temp_dir '/tmp' -s stop

---

## License

Licensed under any of:

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE) or <https://www.apache.org/licenses/LICENSE-2.0>)
- MIT license ([LICENSE-MIT](LICENSE-MIT) or <https://opensource.org/licenses/MIT>)
- CC0 license ([LICENSE-CC0](LICENSE-CC0) or <https://creativecommons.org/publicdomain/zero/1.0/legalcode>)

at your option.

### Contribution

Unless you explicitly state otherwise, any contribution intentionally submitted
for inclusion in the work by you, as defined in the Apache-2.0 license, shall be
licensed as above, without any additional terms or conditions.
