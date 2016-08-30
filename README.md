# ansible-fastly

[![Build Status](https://travis-ci.org/Jimdo/ansible-fastly.svg?branch=master)](https://travis-ci.org/Jimdo/ansible-fastly) [![Ansible Galaxy](https://img.shields.io/badge/galaxy-Jimdo.fastly-blue.svg?style=flat)](https://galaxy.ansible.com/Jimdo/fastly/)

Ansible module to configure services in Fastly

## Installation

``` bash
$ ansible-galaxy install Jimdo.fastly
```

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
```

``` bash
$ ansible-playbook -i localhost, fastly.yml
```
