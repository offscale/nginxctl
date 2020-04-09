Ideas
=====

## Concept 0

    python -m nginxctl -w '/tmp/wwwroot' -p 8080 -i '192.168.2.1'
                       -w '/mnt/webroot' -p 9001 -i 'localhost'
                       --location '/api' 
                       --nest
                           --proxy_pass '192.168.2.1/api'
                           --proxy_http_version '1.1'
                           --proxy_set_header 'Upgrade $http_upgrade'
                           --proxy_set_header 'Connection "Upgrade"'
                           --proxy_set_header 'Host $host'
                       --unnest

### Advantages

  - Extensible to the same level as nginx

### Disadvantages

  - Verbosity

## Concept 1

    python -m nginxctl --root '/tmp/wwwroot'
                       --port 8080
                       --listen '192.168.2.1'
                       --websockets '/api:192.168.2.1/api' 

### Advantages

  - Concision

### Disadvantages

  - Only predefined macros like `websockets`
  - Hides complexity of building your own

## Concept 2

Implement Concept 1, then build a CLI macro system that passes along parameters in a predefined system, so now users/developers can define their own `websockets.macro`.

## Advantages

  - Concision
  - Extensibility

## Disadvantages

  - Complexity of implementation

---

Rollbacks being a big selling point

