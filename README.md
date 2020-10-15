nginxctl
========
[![License](https://img.shields.io/badge/license-Apache--2.0%20OR%20MIT-blue.svg)](https://opensource.org/licenses/Apache-2.0)
![Python version range](https://img.shields.io/badge/python-2.7%20|%203.5%20|%203.6%20|%203.7%20|%203.8%20|3.9-blue.svg)
![Python lint & test](https://github.com/offscale/nginxctl/workflows/Python%20lint%20&%20test/badge.svg)
[![black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Commands for modifying and controlling nginx over the command-line.

## Install dependencies

    pip install -r requirements.txt

## Install package

    pip install .

## Examples

### Serve local directory and then stop server

    $ python -m nginxctl serve --temp_dir '/tmp' \ 
                -b 'server' \
                  --server_name 'localhost' --listen '8080' \
                  -b location '/' \
                    --root '/tmp/wwwroot' \
                  -} \
                -}
    nginx is running. Stop with: /usr/local/bin/nginx -c /tmp/nginx.conf -s stop
    $ curl -Is http://localhost:8080 | head -n1
    127.0.0.1 - - [03/Apr/2020:01:21:45 +1100] "HEAD / HTTP/1.1" 200 0 "-" "curl/7.64.1"
    HTTP/1.1 200 OK
    $ python -m nginxctl nginx --temp_dir '/tmp' -s stop

---

## License

Licensed under either of

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE) or <https://www.apache.org/licenses/LICENSE-2.0>)
- MIT license ([LICENSE-MIT](LICENSE-MIT) or <https://opensource.org/licenses/MIT>)

at your option.

### Contribution

Unless you explicitly state otherwise, any contribution intentionally submitted
for inclusion in the work by you, as defined in the Apache-2.0 license, shall be
dual licensed as above, without any additional terms or conditions.
