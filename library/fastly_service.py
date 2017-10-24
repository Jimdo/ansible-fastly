#!/usr/bin/env python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: fastly_service
author: "Jimdo GmbH"
short_description: Manage and enforce Fastly services
description:
    - Manage and enforce Fastly services
options:
    name:
        required: true
        description:
            - The unique name for the service to create
    fastly_api_key:
        required: false
        description:
            - Fastly API key. If not set then the value of the FASTLY_API_KEY environment variable is used.
    activate_new_version:
        required: false
        default: true
        description:
            - Configures whether newly created versions should be activated automatically
    domains:
        required: true
        description:
            - List of domain names to serve as entry points for your service
    backends:
        required: true
        description:
            - List of backends to service requests from your domains
    healthchecks:
        required: false
        description:
            - List of healthchecks
    conditions:
        required: false
        description:
            - List of conditions
    gzips:
        required: false
        description:
            - List of gzip configurations
    headers:
        required: false
        description:
            - List of headers to manipulate for each request
    response_objects:
        required: false
        description:
            - List of response objects
    vcls:
        required: false
        description:
            - List of vcls
    s3s:
        required: false
        description:
            - List of s3s
    scalyrs:
        required: false
        description:
            - List of scalyrs
    request_settings:
        required: false
        description:
            - List of request settings
    dictionaries:
        required: false
        description:
            - List of dictionaries
'''

EXAMPLES = '''
# General example
- fastly_service:
    name: Example service
    domains:
      - name: test1.example.net
        comment: test1
      - name: test2.example.net
        comment: test2
    backends:
      - name: Backend 1
        port: 80
        address: be1.example.net
      - name: Backend 2
        port: 80
        address: be2.example.net
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
        response: Moved Permanently

# Redirect service
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
        response: Moved Permanently

# VCL example
- fastly_service:
    name: Example service
    domains:
      - name: test1.example.net
        comment: test1
    backends:
      - name: Backend 1
        port: 80
        address: be1.example.net
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

# S3 example
- fastly_service:
    name: Example service
    domains:
      - name: test1.example.net
        comment: test1
    backends:
      - name: Backend 1
        port: 80
        address: be1.example.net
    s3s:
      - name: s3-bucket-logger
        access_key: iam-key
        secret_key: iam-secret
        bucket_name: s3-bucket
        path: /my-app/
        period: 3600


# request_settings example
- fastly_service:
    name: Example service
    domains:
      - name: test1.example.net
        comment: test1
    backends:
      - name: Backend 1
        port: 80
        address: be1.example.net
    request_settings:
      - name: default
        force_ssl: 1
        xff: append_all
'''

import httplib
import urllib
import copy
import logging,traceback

from ansible.module_utils.basic import *

class FastlyResponse(object):
    def __init__(self, http_response):
        self.status = http_response.status
        self.payload = json.loads(http_response.read())


class FastlyObjectEncoder(json.JSONEncoder):
    def default(self, o):
        try:
            return o.to_json()
        except AttributeError:
            return json.JSONEncoder.default(self, o)


class FastlyValidationError(RuntimeError):
    def __init__(self, cls, message):
        self.cls = cls
        self.message = message


class FastlyObject(object):
    schema = {}
    sort_key = None

    def to_json(self):
        return self.__dict__

    def read_config(self, config, validate_choices, param_name):
        required = self.schema[param_name].get('required', True)
        param_type = self.schema[param_name].get('type', 'str')
        default = self.schema[param_name].get('default', None)
        choices = self.schema[param_name].get('choices', None)

        if param_name in config:
            value = config[param_name]
        else:
            value = default

        if value is None and required:
            raise FastlyValidationError(self.__class__.__name__, "Field '%s' is required but not set" % param_name)

        if validate_choices and choices is not None and value not in choices:
            raise FastlyValidationError(self.__class__.__name__,
                                        "Field '%s' must be one of %s" % (param_name, ','.join(choices)))

        if param_type == 'str' and isinstance(value, str):
            value = unicode(value)
        elif param_type == 'intstr':
            try:
                    value = unicode(int(value))
            except ValueError:
                raise FastlyValidationError(self.__class__.__name__,
                                            "Field '%s' with value '%s' couldn't be converted to integer" % (
                                            param_name, value))
        elif param_type == 'int':
            try:
                value = int(value)
            except ValueError:
                raise FastlyValidationError(self.__class__.__name__,
                                            "Field '%s' with value '%s' couldn't be converted to integer" % (
                                            param_name, value))

        return value

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)


class FastlyDomain(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'comment': dict(required=False, type='str', default='')
    }
    sort_key = lambda f: f.name

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.comment = self.read_config(config, validate_choices, 'comment')


class FastlyBackend(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'port': dict(required=False, type='int', default=80),
        'address': dict(required=True, type='str', default=None),
        'comment': dict(required=False, type='str', default=''),
        'shield': dict(required=False, type='str', default=None,
                    choices=[None,'amsterdam-nl','iad-va-us','atl-ga-us','auckland-akl',
                      'brisbane-au','bos-ma-us','ord-il-us','dallas-tx-us','den-co-us',
                      'fjr-ae','frankfurt-de','hongkong-hk','london_city-uk','lax-ca-us',
                      'yyz-on-ca','melbourne-au','miami-fl-us','jfk-ny-us','osaka-jp',
                      'cdg-par-fr','perth-au','sjc-ca-us','sea-wa-us','singapore-sg',
                      'stockholm-bma','sydney-au','tokyo-jp2','wellington-wlg','gru-br-sa']),
        'healthcheck': dict(required=False, type='str', default=None), # TODO implement healthchecks
        # adv options
        'max_conn': dict(required=False, type='intstr', default=200),
        'error_threshold': dict(required=False, type='intstr', default=0),
        # timeouts
        'connect_timeout': dict(required=False, type='intstr', default=1000),
        'first_byte_timeout': dict(required=False, type='intstr', default=15000),
        'between_bytes_timeout': dict(required=False, type='intstr', default=10000),
        # misc
        'request_condition': dict(required=False, type='str', default=''),
        'auto_loadbalance': dict(required=False, type='bool', default=False),
        'weight': dict(required=False, type='int', default=100),
        # ssl options
        'ssl_hostname': dict(required=False, type='str', default=None),
        'ssl_check_cert': dict(required=False, type='bool', default=True),
        'ssl_cert_hostname': dict(required=False, type='str', default=None),
        'ssl_ca_cert': dict(required=False, type='str', default=None),
        # ssl adv options
        'min_tls_version': dict(required=False, type='str', default=None,
                            choices=[None, '1.0', '1.1', '1.2']),
        'max_tls_version': dict(required=False, type='str', default=None,
                            choices=[None, '1.2']),
        'ssl_ciphers': dict(required=False, type='str', default=None),
        'ssl_sni_hostname': dict(required=False, type='str', default=None),
        'ssl_client_cert': dict(required=False, type='str', default=None),
        'ssl_client_key': dict(required=False, type='str', default=None),
    }
    sort_key = lambda f: f.name

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.port = self.read_config(config, validate_choices, 'port')
        self.address = self.read_config(config, validate_choices, 'address')
        self.comment = self.read_config(config, validate_choices, 'comment')
        self.shield = self.read_config(config, validate_choices, 'shield')
        self.healthcheck = self.read_config(config, validate_choices, 'healthcheck')
        self.max_conn = self.read_config(config, validate_choices, 'max_conn')
        self.error_threshold = self.read_config(config, validate_choices, 'error_threshold')
        self.connect_timeout = self.read_config(config, validate_choices, 'connect_timeout')
        self.first_byte_timeout = self.read_config(config, validate_choices, 'first_byte_timeout')
        self.between_bytes_timeout = self.read_config(config, validate_choices, 'between_bytes_timeout')
        self.request_condition = self.read_config(config, validate_choices, 'request_condition')
        self.auto_loadbalance = self.read_config(config, validate_choices, 'auto_loadbalance')
        self.weight = self.read_config(config, validate_choices, 'weight')
        self.ssl_hostname = self.read_config(config, validate_choices, 'ssl_hostname')
        self.ssl_check_cert = self.read_config(config, validate_choices, 'ssl_check_cert')
        if self.ssl_hostname is None:
            self.ssl_hostname = self.address
        self.ssl_cert_hostname = self.read_config(config, validate_choices, 'ssl_cert_hostname')
        self.ssl_ca_cert = self.read_config(config, validate_choices, 'ssl_ca_cert')
        self.min_tls_version = self.read_config(config, validate_choices, 'min_tls_version')
        self.max_tls_version = self.read_config(config, validate_choices, 'max_tls_version')
        self.ssl_ciphers = self.read_config(config, validate_choices, 'ssl_ciphers')
        self.ssl_sni_hostname = self.read_config(config, validate_choices, 'ssl_sni_hostname')
        self.ssl_client_cert = self.read_config(config, validate_choices, 'ssl_client_cert')
        self.ssl_client_key = self.read_config(config, validate_choices, 'ssl_client_key')

class FastlyHealthcheck(FastlyObject):
    schema = {
        'method': dict(required=False, type='str', default='HEAD',
                     choices=['HEAD', 'GET', 'POST']),
        'path': dict(required=False, type='str', default='/'),
        'host': dict(required=True, type='str', default=None),
        'name': dict(required=True, type='str', default=None),
        'expected_response': dict(required=False, type='int', default=200),
        'comment': dict(required=False, type='str', default=''),
        # 'http_version': dict(required=False, type='str', default='1.1',
        #                     choices=['1.0', '1.1']),
        # check frequency
        'threshold': dict(required=False, type='int', default=1),
        'window': dict(required=False, type='int', default=2),
        'initial': dict(required=False, type='int', default=1),
        'check_interval': dict(required=False, type='int', default=60000),
        'timeout': dict(required=False, type='int', default=5000),
    }
    sort_key = lambda f: f.name

    def __init__(self, config, validate_choices):
        self.method = self.read_config(config, validate_choices, 'method')
        self.path = self.read_config(config, validate_choices, 'path')
        self.host = self.read_config(config, validate_choices, 'host')
        self.name = self.read_config(config, validate_choices, 'name')
        self.expected_response = self.read_config(config, validate_choices, 'expected_response')
        self.comment = self.read_config(config, validate_choices, 'comment')
        # self.http_version = self.read_config(config, validate_choices, 'name')
        # check frequency
        self.threshold = self.read_config(config, validate_choices, 'threshold')
        self.window = self.read_config(config, validate_choices, 'window')
        self.initial = self.read_config(config, validate_choices, 'initial')
        self.check_interval = self.read_config(config, validate_choices, 'check_interval')
        self.timeout = self.read_config(config, validate_choices, 'timeout')

class FastlyCondition(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'comment': dict(required=False, type='str', default=''),
        'priority': dict(required=False, type='intstr', default='0'),
        'statement': dict(required=True, type='str'),
        'type': dict(required=True, type='str', default=None,
                     choices=['REQUEST', 'PREFETCH', 'CACHE', 'RESPONSE']),
    }
    sort_key = lambda f: f.name

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.comment = self.read_config(config, validate_choices, 'comment')
        self.priority = self.read_config(config, validate_choices, 'priority')
        self.statement = self.read_config(config, validate_choices, 'statement')
        self.type = self.read_config(config, validate_choices, 'type')


class FastlyGzip(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'cache_condition': dict(required=False, type='str', default=''),
        'content_types': dict(required=False, type='str', default='text/html application/x-javascript text/css application/javascript text/javascript application/json application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/xml font/eot font/opentype font/otf image/svg+xml image/vnd.microsoft.icon text/plain text/xml'),
        'extensions': dict(required=False, type='str', default='css js html eot ico otf ttf json'),
    }
    sort_key = lambda f: f.name

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.cache_condition = self.read_config(config, validate_choices, 'cache_condition')
        self.content_types = self.read_config(config, validate_choices, 'content_types')
        self.extensions = self.read_config(config, validate_choices, 'extensions')


class FastlyHeader(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'action': dict(required=False, type='str', default='set',
                       choices=['set', 'append', 'delete', 'regex', 'regex_repeat']),
        'dst': dict(required=True, type='str', default=None),
        'ignore_if_set': dict(required=False, type='intstr', default='0'),
        'priority': dict(required=False, type='intstr', default='100'),
        'regex': dict(required=False, type='str', default=''),
        'type': dict(required=True, type='str', default=None,
                     choices=['request', 'fetch', 'cache', 'response']),
        'src': dict(required=True, type='str', default=None),
        'substitution': dict(required=False, type='str', default='')
    }
    sort_key = lambda f: f.name

    def __init__(self, config, validate_choices):
        self.action = self.read_config(config, validate_choices, 'action')
        self.dst = self.read_config(config, validate_choices, 'dst')
        self.ignore_if_set = self.read_config(config, validate_choices, 'ignore_if_set')
        self.name = self.read_config(config, validate_choices, 'name')
        self.priority = self.read_config(config, validate_choices, 'priority')
        self.regex = self.read_config(config, validate_choices, 'regex')
        self.type = self.read_config(config, validate_choices, 'type')
        self.src = self.read_config(config, validate_choices, 'src')
        self.substitution = self.read_config(config, validate_choices, 'substitution')

class FastlyResponseObject(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'request_condition': dict(required=False, type='str', default=''),
        'response': dict(required=False, type='str', default='Ok'),
        'status': dict(required=False, type='intstr', default='200')
    }
    sort_key = lambda f: f.name

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.request_condition = self.read_config(config, validate_choices, 'request_condition')
        self.response = self.read_config(config, validate_choices, 'response')
        self.status = self.read_config(config, validate_choices, 'status')

class FastlyVCL(FastlyObject):
    schema = {
        'content': dict(required=False, type='str', default=''),
        'main': dict(required=False, type='bool', default=True),
        'name': dict(required=True, type='str', default=None),
    }
    sort_key = lambda f: f.name

    def __init__(self, config, validate_choices):
        self.content = self.read_config(config, validate_choices, 'content')
        self.main = self.read_config(config, validate_choices, 'main')
        self.name = self.read_config(config, validate_choices, 'name')

class FastlyS3(FastlyObject):
    # see https://docs-next.fastly.com/api/logging#logging_s3
    schema = {
        'name': dict(required=True, type='str', default=None),
        'format': dict(required=False, type='str', default='%h %l %u %t %r %>s'),
        'format_version': dict(required=False, type='intstr', default='1'),
        'bucket_name': dict(required=True, type='str', default=None),
        'access_key': dict(required=True, type='str', default=None),
        'secret_key': dict(required=True, type='str', default=None),
        'period': dict(required=False, type='intstr', default='3600'),
        'path': dict(required=False, type='str', default=''),
        'domain': dict(required=False, type='str', default=''),
        'gzip_level': dict(required=False, type='intstr', default='0'),
        'redundancy': dict(required=False, type='str', default='standard',
                        choices=['standard','reduced_redundancy']),
        'response_condition': dict(required=False, type='str', default=''),
        # adv settings not in gui
        'server_side_encryption': dict(required=False, type='str', default=None,
                        choices=[None, 'AES256', 'aws:kms']),
        'message_type': dict(required=False, type='str', default='classic',
                       choices=['classic', 'loggly', 'logplex', 'blank']),
        'server_side_encryption_kms_key_id': dict(required=False, type='str', default=''),
        'timestamp_format': dict(required=False, type='str', default=''),
        # in json response but not in documentation or gui
        'public_key': dict(required=False, type='str', default=''),
    }
    sort_key = lambda f: f.name

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.format = self.read_config(config, validate_choices, 'format')
        self.format_version = self.read_config(config, validate_choices, 'format_version')
        self.bucket_name = self.read_config(config, validate_choices, 'bucket_name')
        self.access_key = self.read_config(config, validate_choices, 'access_key')
        self.secret_key = self.read_config(config, validate_choices, 'secret_key')
        self.period = self.read_config(config, validate_choices, 'period')
        self.path = self.read_config(config, validate_choices, 'path')
        self.domain = self.read_config(config, validate_choices, 'domain')
        self.gzip_level = self.read_config(config, validate_choices, 'gzip_level')
        self.redundancy = self.read_config(config, validate_choices, 'redundancy')
        self.response_condition = self.read_config(config, validate_choices, 'response_condition')
        self.server_side_encryption_kms_key_id = self.read_config(config, validate_choices, 'server_side_encryption_kms_key_id')
        self.message_type = self.read_config(config, validate_choices, 'message_type')
        self.server_side_encryption = self.read_config(config, validate_choices, 'server_side_encryption')
        self.timestamp_format = self.read_config(config, validate_choices, 'timestamp_format')
        self.public_key = self.read_config(config, validate_choices, 'public_key')

class FastlyScalyr(FastlyObject):
    # see https://docs-next.fastly.com/api/logging#logging_scalyr
    schema = {
        'name': dict(required=True, type='str', default=None),
        'format': dict(required=False, type='str', default='%h %l %u %t %r %>s'),
        # 'format_version': dict(required=False, type='intstr', default='1'),
        'token': dict(required=True, type='str', default=None),
        'response_condition': dict(required=False, type='str', default=''),
    }
    sort_key = lambda f: f.name

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.format = self.read_config(config, validate_choices, 'format')
        # self.format_version = self.read_config(config, validate_choices, 'format_version')
        self.token = self.read_config(config, validate_choices, 'token')
        self.response_condition = self.read_config(config, validate_choices, 'response_condition')

class FastlyRequestSetting(FastlyObject):
    schema = {
        # basic
        'name': dict(required=True, type='str', default=None),
        'action': dict(required=False, type='str', default=None),
        'force_ssl': dict(required=False, type='intstr', default='0'),
        'xff': dict(required=False, type='str', default='leave',
                        choices=['clear', 'leave', 'append', 'append_all', 'overwrite']),
        # advanced
        'default_host': dict(required=False, type='str', default=None),
        'timer_support': dict(required=False, type='str', default=None),
        'max_stale_age': dict(required=False, type='str', default=None),
        'force_miss': dict(required=False, type='str', default=None),
        'bypass_busy_wait': dict(required=False, type='str', default=None),
        'hash_keys': dict(required=False, type='str', default=None),
        # condition
        'request_condition': dict(required=False, type='str', default='')
    }
    sort_key = lambda f: f.name

    def __init__(self, config, validate_choices):
        # basic
        self.name = self.read_config(config, validate_choices, 'name')
        self.action = self.read_config(config, validate_choices, 'action')
        self.force_ssl = self.read_config(config, validate_choices, 'force_ssl')
        self.xff = self.read_config(config, validate_choices, 'xff')
        # advanced
        self.default_host = self.read_config(config, validate_choices, 'default_host')
        self.timer_support = self.read_config(config, validate_choices, 'timer_support')
        self.max_stale_age = self.read_config(config, validate_choices, 'max_stale_age')
        self.force_miss = self.read_config(config, validate_choices, 'force_miss')
        self.bypass_busy_wait = self.read_config(config, validate_choices, 'bypass_busy_wait')
        self.hash_keys = self.read_config(config, validate_choices, 'hash_keys')
        # condition
        self.request_condition = self.read_config(config, validate_choices, 'request_condition')

class FastlyDictionary(FastlyObject):
    # see https://docs.fastly.com/api/config#dictionary
    schema = {
        'name': dict(required=True, type='str', default=None),
    }
    sort_key = lambda f: f.name

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')

class FastlySettings(object):
    def __init__(self, settings, validate_choices = True):
        self.domains = []
        self.healthchecks = []
        self.backends = []
        self.conditions = []
        self.gzips = []
        self.headers = []
        self.response_objects = []
        self.vcls = []
        self.s3s = []
        self.scalyrs = []
        self.request_settings = []
        self.dictionaries = []

        if 'domains' in settings and settings['domains'] is not None:
            for domain in settings['domains']:
                self.domains.append(FastlyDomain(domain, validate_choices))

        if 'healthchecks' in settings and settings['healthchecks'] is not None:
            for healthcheck in settings['healthchecks']:
                self.healthchecks.append(FastlyHealthcheck(healthcheck, validate_choices))

        if 'backends' in settings and settings['backends'] is not None:
            for backend in settings['backends']:
                self.backends.append(FastlyBackend(backend, validate_choices))

        if 'conditions' in settings and settings['conditions'] is not None:
            for condition in settings['conditions']:
                self.conditions.append(FastlyCondition(condition, validate_choices))

        if 'gzips' in settings and settings['gzips'] is not None:
            for gzip in settings['gzips']:
                self.gzips.append(FastlyGzip(gzip, validate_choices))

        if 'headers' in settings and settings['headers'] is not None:
            for header in settings['headers']:
                self.headers.append(FastlyHeader(header, validate_choices))

        if 'response_objects' in settings and settings['response_objects'] is not None:
            for response_object in settings['response_objects']:
                self.response_objects.append(FastlyResponseObject(response_object, validate_choices))

        if 'vcls' in settings and settings['vcls'] is not None:
            for vcl in settings['vcls']:
                self.vcls.append(FastlyVCL(vcl, validate_choices))

        if 's3s' in settings and settings['s3s'] is not None:
            for s3 in settings['s3s']:
                self.s3s.append(FastlyS3(s3, validate_choices))

        if 'scalyrs' in settings and settings['scalyrs'] is not None:
            for scalyr in settings['scalyrs']:
                self.scalyrs.append(FastlyScalyr(scalyr, validate_choices))

        if 'request_settings' in settings and settings['request_settings'] is not None:
            for request_setting in settings['request_settings']:
                self.request_settings.append(FastlyRequestSetting(request_setting, validate_choices))

        if 'dictionaries' in settings and settings['dictionaries'] is not None:
            for dictionary in settings['dictionaries']:
                self.dictionaries.append(FastlyDictionary(dictionary, validate_choices))

    def __eq__(self, other):
        return sorted(self.domains, key=FastlyDomain.sort_key) == sorted(other.domains, key=FastlyDomain.sort_key) \
               and sorted(self.healthchecks, key=FastlyHealthcheck.sort_key) == sorted(other.healthchecks, key=FastlyHealthcheck.sort_key) \
               and sorted(self.backends, key=FastlyBackend.sort_key) == sorted(other.backends, key=FastlyBackend.sort_key) \
               and sorted(self.conditions, key=FastlyCondition.sort_key) == sorted(other.conditions, key=FastlyCondition.sort_key) \
               and sorted(self.gzips, key=FastlyGzip.sort_key) == sorted(other.gzips, key=FastlyGzip.sort_key) \
               and sorted(self.headers, key=FastlyHeader.sort_key) == sorted(other.headers, key=FastlyHeader.sort_key) \
               and sorted(self.response_objects, key=FastlyResponseObject.sort_key) == sorted(other.response_objects, key=FastlyResponseObject.sort_key) \
               and sorted(self.vcls, key=FastlyVCL.sort_key) == sorted(other.vcls, key=FastlyVCL.sort_key) \
               and sorted(self.s3s, key=FastlyS3.sort_key) == sorted(other.s3s, key=FastlyS3.sort_key) \
               and sorted(self.scalyrs, key=FastlyScalyr.sort_key) == sorted(other.scalyrs, key=FastlyScalyr.sort_key) \
               and sorted(self.request_settings, key=FastlyRequestSetting.sort_key) == sorted(other.request_settings, key=FastlyRequestSetting.sort_key) \
               and sorted(self.dictionaries, key=FastlyDictionary.sort_key) == sorted(other.dictionaries, key=FastlyDictionary.sort_key)

    def __ne__(self, other):
        return not self.__eq__(other)


class FastlyVersion(object):
    def __init__(self, version_settings):
        self.settings = FastlySettings(version_settings, False)
        self.number = version_settings['number']
        self.active = version_settings['active']


class FastlyService(object):
    def __init__(self, service_settings):
        self.active_version = None
        if service_settings['active_version'] is not None:
            self.active_version = FastlyVersion(service_settings['active_version'])

        self.latest_version = None
        if service_settings['version'] is not None:
            self.latest_version = FastlyVersion(service_settings['version'])

        self.id = service_settings['id']
        self.name = service_settings['name']


class FastlyClient(object):
    FASTLY_API_HOST = 'api.fastly.com'
    setting_name_plurals = {
        'request_setting': 'request_settings',
        'dictionary': 'dictionaries'
    }
    setting_names = [
        'domain',
        'condition',
        'healthcheck',
        'backend',
        'gzip',
        'header',
        'response_object',
        'vcl',
        's3',
        'scalyr',
        'request_setting',
        'dictionary',
    ]
    api_endpoints = {
        'domain': '/service/%s/version/%s/domain',
        'healthcheck': '/service/%s/version/%s/healthcheck',
        'backend': '/service/%s/version/%s/backend',
        'condition': '/service/%s/version/%s/condition',
        'gzip': '/service/%s/version/%s/gzip',
        'header': '/service/%s/version/%s/header',
        'response_object': '/service/%s/version/%s/response_object',
        'vcl': '/service/%s/version/%s/vcl',
        's3': '/service/%s/version/%s/logging/s3',
        'scalyr': '/service/%s/version/%s/logging/scalyr',
        'request_setting': '/service/%s/version/%s/request_settings',
        'dictionary': '/service/%s/version/%s/dictionary',
    }

    def __init__(self, fastly_api_key):
        self.fastly_api_key = fastly_api_key

    def _request(self, path, method='GET', payload=None, headers=None):
        if headers is None:
            headers = {}
        headers.update({
            'Fastly-Key': self.fastly_api_key,
            'Content-Type': 'application/json'
        })

        body = None
        if payload is not None:
            body = json.dumps(payload, cls=FastlyObjectEncoder)

        conn = httplib.HTTPSConnection(self.FASTLY_API_HOST)
        conn.request(method, path, body, headers)
        return FastlyResponse(conn.getresponse())

    def call_api(self, action, setting_name, service_id, version, setting, current_setting=None):
        url = self.api_endpoints[setting_name]
        logging.debug('action:%s setting_name:%s url:%s setting:%s' % (action, setting_name, url, setting.to_json()))

        # fix up empty request_condition for request_setting
        if (
                action in ["create", "update"] and
                setting_name in ["request_setting"] and
                setting.request_condition == ''
            ):
            setting = copy.deepcopy(setting)
            setting.request_condition = None
            logging.debug('request_condition empty for setting_name:%s setting:%s' % (setting_name, setting.to_json()))

        # fix up empty response_condition for s3, scalyr
        if (
                action in ["create", "update"] and
                setting_name in ["s3", "scalyr"] and
                setting.response_condition == ''
            ):
            setting = copy.deepcopy(setting)
            setting.response_condition = None
            logging.debug('response_condition empty for setting_name:%s setting:%s' % (setting_name, setting.to_json()))

        if action == "create":
            # url format - /service/%s/version/%s/SETTING
            response = self._request(url % (service_id, version), 'POST', setting)
        elif action == "update":
            # url format - /service/%s/version/%s/SETTING/OLD_NAME
            url += '/%s'
            name_to_update = urllib.quote(current_setting.name)
            logging.debug('url:%s name_to_update:%s setting:%s' % (url, name_to_update, setting.to_json()))
            response = self._request(url % (service_id, version, name_to_update), 'PUT', setting)
        elif action == "delete":
            # url format - /service/%s/version/%s/SETTING/OLD_NAME
            url += '/%s'
            name_to_delete = urllib.quote(setting.name)
            response = self._request(url % (service_id, version, name_to_delete), 'DELETE', setting)

        if response.status == 200:
            if action == "delete":
                return True
            return response.payload
        else:
            raise Exception("Error trying to %s %s for service %s, version %s (%s)" % (
                action, setting_name, service_id, version, response.payload['detail']))

    def get_service_by_name(self, service_name):
        response = self._request('/service/search?name=%s' % urllib.quote(service_name))
        if response.status == 200:
            service_id = response.payload['id']
            return self.get_service(service_id)
        elif response.status == 404:
            return None
        else:
            raise Exception("Error searching for service '%s'" % service_name)

    def get_service(self, service_id):
        response = self._request('/service/%s/details' % service_id)
        if response.status == 200:
            return FastlyService(response.payload)
        elif response.status == 404:
            return None
        else:
            raise Exception("Error fetching service details for service '%s'" % service_id)

    def create_service(self, service_name):
        response = self._request('/service', 'POST', {'name': service_name})
        if response.status == 200:
            return self.get_service(response.payload['id'])
        else:
            raise Exception("Error creating service with name '%s'" % service_name)

    def delete_service(self, service_name, deactivate_active_version=True):
        service = self.get_service_by_name(service_name)
        if service is None:
            return False

        if service.active_version is not None and deactivate_active_version:
            self.deactivate_version(service.id, service.active_version.number)

        response = self._request('/service/%s' % urllib.quote(service.id), 'DELETE')
        if response.status == 200:
            return True
        else:
            raise Exception("Error deleting service with name '%s' (%s)" % (service_name, response.payload['detail']))

    def create_version(self, service_id):
        response = self._request('/service/%s/version' % service_id, 'POST')
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating new version for service %s" % service_id)

    def clone_version(self, service_id, version):
        response = self._request('/service/%s/version/%s/clone' % (service_id, version), 'PUT')
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error cloning version %s for service %s" % (version, service_id))

    def activate_version(self, service_id, version):
        response = self._request('/service/%s/version/%s/activate' % (service_id, version), 'PUT')
        if response.status == 200:
            return response.payload
        else:
            raise Exception(
                "Error activating version %s for service %s (%s)" % (version, service_id, response.payload['detail']))

    def deactivate_version(self, service_id, version):
        response = self._request('/service/%s/version/%s/deactivate' % (service_id, version), 'PUT')
        if response.status == 200:
            return response.payload
        else:
            raise Exception(
                "Error deactivating version %s for service %s (%s)" % (version, service_id, response.payload['detail']))

class FastlyStateEnforcerResult(object):
    def __init__(self, changed, actions, service):
        self.changed = changed
        self.actions = actions
        self.service = service


class FastlyStateEnforcer(object):
    def __init__(self, client):
        self.client = client

    def get_setting_names(self):
        return self.client.setting_names

    def get_setting_name_plural(self, setting_name):
        return self.client.setting_name_plurals.get(setting_name, setting_name+'s')

    def apply_settings(self, service_name, fastly_settings, activate_new_version=True):

        actions = []

        service = self.client.get_service_by_name(service_name)

        if service is None:
            service = self.client.create_service(service_name)
            actions.append("Created new service %s" % service_name)

        if activate_new_version:
            current_version = service.active_version
        else:
            current_version = service.latest_version

        if current_version is None:
            # create new version
            version = self.client.create_version(service.id)
            self.deploy_version_with_settings(service.id, version['number'], fastly_settings, activate_new_version)
            actions.append("Deployed new version because service has no active version")
        elif fastly_settings != current_version.settings:
            # clone existing version
            version = self.client.clone_version(service.id, current_version.number)
            self.deploy_version_with_settings(service.id, version['number'], fastly_settings, activate_new_version, current_version.settings)
            actions.append("Deployed new version because settings are not up to date")

        changed = len(actions) > 0
        service = self.client.get_service(service.id)
        return FastlyStateEnforcerResult(actions=actions, changed=changed, service=service)

    def deploy_version_with_settings(self, service_id, version_number, settings, activate_version, current_settings=None):

        for setting_name in self.get_setting_names():
            setting_name_plural = self.get_setting_name_plural(setting_name)
            new_items = getattr(settings, setting_name_plural)
            current_items = getattr(current_settings, setting_name_plural, None)
            # compare new with current
            for item in new_items:
                action = None
                current_item = None
                # if no current_settings, then its new and no current items
                if current_items is None:
                    action = "create"
                else:
                    # otherwise - look it up
                    current_item = next((x for x in current_items if x.name == item.name), None)
                    if current_item is None:
                        # create if not found
                        action = "create"
                    elif current_item != item:
                        logging.info('found - different - setting_name:%s item:%s current_item:%s' % (setting_name, item.to_json(), current_item.to_json()))
                        # update and remove from curr_item, leftover items in current_items will get deleted
                        action = "update"
                        current_items.remove(current_item)
                    else:
                        logging.info('found - same - setting_name:%s item:%s current_item:%s' % (setting_name, item.to_json(), current_item.to_json()))
                        # no change, leave alone but remove from curr_item, leftover items in current_items will get deleted
                        current_items.remove(current_item)
                # perform the update or create action or skip if found but same
                logging.debug('action:%s setting_name:%s item:%s' % (action, setting_name, item.to_json()))
                if action == "update":
                    logging.debug('curr_item:%s' % (current_item.to_json()))
                    # exists - update
                    self.client.call_api("update", setting_name, service_id, version_number, item, current_item)
                elif action == "create":
                    self.client.call_api("create", setting_name, service_id, version_number, item)

            # any items in current_settings are not needed, remove
            if current_items is not None:
                for item in current_items:
                    self.client.call_api("delete", setting_name, service_id, version_number, item)

        if activate_version:
            self.client.activate_version(service_id, version_number)

    def delete_service(self, service_name):
        service = self.client.get_service_by_name(service_name)

        if service is None:
            return FastlyStateEnforcerResult(actions=[], changed=False, service=None)

        actions = []

        changed = self.client.delete_service(service_name)

        if changed:
            actions.append('Deleted service %s' % service_name)

        return FastlyStateEnforcerResult(actions=actions, changed=changed, service=service)


class FastlyServiceModule(object):
    def __init__(self):
        self.module = AnsibleModule(
            argument_spec=dict(
                state=dict(default='present', choices=['present', 'absent'], type='str'),
                fastly_api_key=dict(no_log=True, type='str'),
                name=dict(required=True, type='str'),
                activate_new_version=dict(required=False, type='bool', default=True),
                domains=dict(default=None, required=True, type='list'),
                healthchecks=dict(default=None, required=False, type='list'),
                backends=dict(default=None, required=True, type='list'),
                conditions=dict(default=None, required=False, type='list'),
                gzips=dict(default=None, required=False, type='list'),
                headers=dict(default=None, required=False, type='list'),
                response_objects=dict(default=None, required=False, type='list'),
                vcls=dict(default=None, required=False, type='list'),
                s3s=dict(default=None, required=False, type='list'),
                scalyrs=dict(default=None, required=False, type='list'),
                request_settings=dict(default=None, required=False, type='list'),
                dictionaries=dict(default=None, required=False, type='list'),
            ),
            supports_check_mode=False
        )

    def enforcer(self):
        fastly_api_key = self.module.params['fastly_api_key']
        if not fastly_api_key:
            if 'FASTLY_API_KEY' in os.environ:
                fastly_api_key = os.environ['FASTLY_API_KEY']
            else:
                self.module.fail_json(msg="A Fastly API key is required for this module. Please set it and try again")
        return FastlyStateEnforcer(FastlyClient(fastly_api_key))

    def settings(self):
        try:
            return FastlySettings({
                'domains': self.module.params['domains'],
                'healthchecks': self.module.params['healthchecks'],
                'backends': self.module.params['backends'],
                'conditions': self.module.params['conditions'],
                'gzips': self.module.params['gzips'],
                'headers': self.module.params['headers'],
                'response_objects': self.module.params['response_objects'],
                'vcls': self.module.params['vcls'],
                's3s': self.module.params['s3s'],
                'scalyrs': self.module.params['scalyrs'],
                'request_settings': self.module.params['request_settings'],
                'dictionaries': self.module.params['dictionaries'],
            })
        except FastlyValidationError as err:
            self.module.fail_json(msg='Error in ' + err.cls + ': ' + err.message, stacktrace=traceback.format_exc())
        except Exception as err:
            self.module.fail_json(msg=err.message, stacktrace=traceback.format_exc())

    def run(self):
        try:
            enforcer = self.enforcer()
            service_name = self.module.params['name']
            activate_new_version = self.module.params['activate_new_version']

            if self.module.params['state'] == 'absent':
                result = enforcer.delete_service(service_name)

                service_id = None
                if result.service is not None:
                    service_id = result.service.id

                self.module.exit_json(changed=result.changed, service_id=service_id, actions=result.actions)
            else:
                result = enforcer.apply_settings(service_name, self.settings(), activate_new_version)
                self.module.exit_json(changed=result.changed, service_id=result.service.id, actions=result.actions)

        except Exception as err:
            self.module.fail_json(msg=err.message, stacktrace=traceback.format_exc())


def main():
    fastly_module = FastlyServiceModule()
    fastly_module.run()


if __name__ == '__main__':
    main()
