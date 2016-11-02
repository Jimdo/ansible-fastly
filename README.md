# ansible-fastly

[![Build Status](https://travis-ci.org/Jimdo/ansible-fastly.svg?branch=master)](https://travis-ci.org/Jimdo/ansible-fastly) [![Ansible Galaxy](https://img.shields.io/badge/galaxy-Jimdo.fastly-blue.svg?style=flat)](https://galaxy.ansible.com/Jimdo/fastly/)

Ansible module to configure services in Fastly

## Installation

``` bash
$ ansible-galaxy install Jimdo.fastly
```

## Documentation

### Module options

| Name                 | Required | Description                                                                                   | Default |
|:---------------------|:---------|:----------------------------------------------------------------------------------------------|:--------|
| name                 | true     | The unique name for the service to create                                                     |         |
| fastly_api_key       | false    | Fastly API key. If not set then the value of the FASTLY_API_KEY environment variable is used. |         |
| activate_new_version | false    | Configures whether newly created versions should be activated automatically                   | true    |
| domains              | true     | List of domain names to serve as entry points for your service                                |         |
| backends             | true     | List of backends to service requests from your domains                                        |         |
| conditions           | false    | List of conditions                                                                            |         |
| gzips                | false    | List of gzip configurations                                                                   |         |
| headers              | false    | List of headers to manipulate for each request                                                |         |
| response_objects     | false    | List of response objects                                                                      |         |
| vcls                 | false    | List of VCLs
| s3s                  | false    | List of S3 log entries

### Condition

[Fastly documentation](https://docs.fastly.com/api/config#condition)

| Field     | Required | Type                                                    | Default |
|:----------|:---------|:--------------------------------------------------------|:--------|
| name      | true     | string                                                  |         |
| comment   | false    | string                                                  |         |
| priority  | false    | integer                                                 | 0       |
| statement | true     | string                                                  |         |
| type      | true     | enum ('REQUEST', 'PREFETCH', 'CACHE', 'RESPONSE')       |         |

### Backends

[Fastly documentation](https://docs.fastly.com/api/config#backend)

| Field                 | Required | Type                                                    | Default |
|:----------------------|:---------|:--------------------------------------------------------|:--------|
| name                  | true     | string                                                  |         |
| port                  | false    | integer                                                 | 80      |
| address               | true     | string                                                  |         |
| comment               | false    | string                                                  |         |
| shield                | false    | string                                                  |         |
| max_conn              | false    | integer                                                 | 200     |
| error_threshold       | false    | integer                                                 | 0       |
| connect_timeout       | false    | integer                                                 | 1000    |
| first_byte_timeout    | false    | integer                                                 | 15000   |
| between_bytes_timeout | false    | integer                                                 | 10000   |
| request_condition     | false    | string                                                  |         |
| auto_loadbalance      | false    | bool                                                    | false   |
| weight                | false    | integer                                                 | 0       |
| ssl_hostname          | false    | string                                                  |         |
| ssl_check_cert        | false    | bool                                                    | true    |
| ssl_cert_hostname     | false    | string                                                  |         |
| ssl_ca_cert           | false    | string                                                  |         |
| min_tls_version       | false    | string                                                  |         |
| max_tls_version       | false    | string                                                  |         |
| ssl_ciphers           | false    | string                                                  |         |
| ssl_sni_hostname      | false    | string                                                  |         |
| ssl_client_cert       | false    | string                                                  |         |
| ssl_client_key        | false    | string                                                  |         |

### Header

[Fastly documentation](https://docs.fastly.com/api/config#header)

| Field         | Required | Type                                                      | Default |
|:--------------|:---------|:----------------------------------------------------------|:--------|
| name          | true     | string                                                    |         |
| action        | false    | enum ('set', 'append', 'delete', 'regex', 'regex_repeat') | set     |
| dst           | true     | string                                                    |         |
| ignore_if_set | false    | int (one of [0,1])                                        | 0       |
| priority      | false    | int                                                       | 100     |
| regex         | false    | string                                                    |         |
| type          | true     | enum ('request', 'fetch', 'cache', 'response')            |         |
| src           | true     | string                                                    |         |
| substitution  | false    | string                                                    |         |

### Response Object

[Fastly documentation](https://docs.fastly.com/api/config#response_object)

| Field             | Required | Type                                                      | Default |
|:------------------|:---------|:----------------------------------------------------------|:--------|
| name              | true     | string                                                    |         |
| request_condition | false    | string                                                    |         |
| response          | false    | string                                                    | Ok      |
| status            | false    | int                                                       | 200     |

### Request Settings

[Fastly documentation](https://docs.fastly.com/api/config#request_settings)

| Field             | Required | Type                                                        | Default |
|:------------------|:---------|:------------------------------------------------------------|:--------|
| name              | true     | string                                                      |         |
| request_condition | false    | string                                                      |         |
| action            | false    | string                                                      |         |
| force_ssl         | false    | int                                                         | 0       |
| xff               | false    | enum('clear', 'leave', 'append', 'append_all', 'overwrite') | leave   |
| default_host      | false    | string                                                      |         |
| timer_support     | false    | string                                                      |         |
| max_stale_age     | false    | string                                                      |         |
| force_miss        | false    | string                                                      |         |
| bypass_busy_wait  | false    | string                                                      |         |
| hash_keys         | false    | string                                                      |         |

### VCL

[Fastly documentation](https://docs.fastly.com/api/config#vcl)

| Field             | Required | Type                                                      | Default |
|:------------------|:---------|:----------------------------------------------------------|:--------|
| name              | true     | string                                                    |         |
| content           | true     | string                                                    |         |
| main              | false    | bool                                                      | true    |

### S3 log entries

[Fastly documentation](https://docs-next.fastly.com/api/logging#logging_s3)

| Field                             | Required | Type                                            | Default            |
|:----------------------------------|:---------|:------------------------------------------------|:-------------------|
| name                              | true     | str                                             |                    |
| format                            | false    | str                                             | %h %l %u %t %r %>s |
| format_version                    | false    | intstr                                          | 1                  |
| bucket_name                       | true     | str                                             |                    |
| access_key                        | true     | str                                             |                    |
| secret_key                        | true     | str                                             |                    |
| period                            | false    | intstr                                          | 3600               |
| path                              | false    | str                                             |                    |
| domain                            | false    | str                                             |                    |
| gzip_level                        | false    | intstr                                          | 0                  |
| redundancy                        | false    | enum('standard','reduced_redundancy')           | standard           |
| response_condition                | false    | str                                             |                    |
| server_side_encryption            | false    | enum(None, 'AES256', 'aws:kms')                 |                    |
| message_type                      | false    | enum('classic', 'loggly', 'logplex', 'blank')   | classic            |
| server_side_encryption_kms_key_id | false    | str                                             |                    |
| timestamp_format                  | false    | str                                             |                    |

## Examples

### Using the fastly_service module in a Playbook

``` yml
---
- hosts: localhost
  connection: local
  gather_facts: False
  roles:
    - Jimdo.fastly
  tasks:
    - fastly_service:
        name: Redirect service
        domains:
          - name: test1.example.net
            comment: redirect domain
        backends:
          - name: localhost
            port: 80
            address: 127.0.0.1
        headers:
          - name: Set Location header
            dst: http.Location
            type: response
            action: set
            src: http://test3.example.net req.url.path
            ignore_if_set: 0
            priority: 10
        response_objects:
          - name: Set 301 status code
            status: 301
        vcls:
          - name: main
            main: true
            content: |
                sub vcl_hit {
                #FASTLY hit
                 if (!obj.cacheable) {
                   return(pass);
                 }
                 return(deliver);
                }
        s3s:
          - name: s3-bucket-logger
            access_key: iam-key
            secret_key: iam-secret
            bucket_name: s3-bucket
            path: /my-app/
            period: 3600

```

``` bash
$ ansible-playbook -i localhost, fastly.yml
```
