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
        'shield': dict(required=False, type='str', default=None), # TODO get list of POPs
        # 'healthcheck': dict(required=False, type='str', default=None), # TODO implement healtchecks
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
        'weight': dict(required=False, type='int', default=0),
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
        'content_types': dict(required=False, type='str', default=''),
        'extensions': dict(required=False, type='str', default=''),
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

class FastlySettings(object):
    def __init__(self, settings, validate_choices = True):
        self.domains = []
        self.backends = []
        self.conditions = []
        self.gzips = []
        self.headers = []
        self.response_objects = []
        self.vcls = []
        self.s3s = []
        self.scalyrs = []
        self.request_settings = []

        if 'domains' in settings and settings['domains'] is not None:
            for domain in settings['domains']:
                self.domains.append(FastlyDomain(domain, validate_choices))

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

    def __eq__(self, other):
        return sorted(self.domains, key=FastlyDomain.sort_key) == sorted(other.domains, key=FastlyDomain.sort_key) \
               and sorted(self.backends, key=FastlyBackend.sort_key) == sorted(other.backends, key=FastlyBackend.sort_key) \
               and sorted(self.conditions, key=FastlyCondition.sort_key) == sorted(other.conditions, key=FastlyCondition.sort_key) \
               and sorted(self.gzips, key=FastlyGzip.sort_key) == sorted(other.gzips, key=FastlyGzip.sort_key) \
               and sorted(self.headers, key=FastlyHeader.sort_key) == sorted(other.headers, key=FastlyHeader.sort_key) \
               and sorted(self.response_objects, key=FastlyResponseObject.sort_key) == sorted(other.response_objects, key=FastlyResponseObject.sort_key) \
               and sorted(self.vcls, key=FastlyVCL.sort_key) == sorted(other.vcls, key=FastlyVCL.sort_key) \
               and sorted(self.s3s, key=FastlyS3.sort_key) == sorted(other.s3s, key=FastlyS3.sort_key) \
               and sorted(self.scalyrs, key=FastlyScalyr.sort_key) == sorted(other.scalyrs, key=FastlyScalyr.sort_key) \
               and sorted(self.request_settings, key=FastlyRequestSetting.sort_key) == sorted(other.request_settings, key=FastlyRequestSetting.sort_key)

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

    def create_domain(self, service_id, version, domain):
        response = self._request('/service/%s/version/%s/domain' % (service_id, version), 'POST', domain)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating domain for for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def create_backend(self, service_id, version, backend):
        response = self._request('/service/%s/version/%s/backend' % (service_id, version), 'POST', backend)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating backend for for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def create_condition(self, service_id, version, condition):
        response = self._request('/service/%s/version/%s/condition' % (service_id, version), 'POST', condition)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating condition for for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def create_gzip(self, service_id, version, gzip):
        response = self._request('/service/%s/version/%s/gzip' % (service_id, version), 'POST',
                                 gzip)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating gzip for for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def create_header(self, service_id, version, header):
        response = self._request('/service/%s/version/%s/header' % (service_id, version), 'POST', header)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating header for for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def create_response_object(self, service_id, version, response_object):
        response = self._request('/service/%s/version/%s/response_object' % (service_id, version), 'POST',
                                 response_object)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating response object for for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def create_vcl(self, service_id, version, vcl):
        response = self._request('/service/%s/version/%s/vcl' % (service_id, version), 'POST', vcl)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating vcl for for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def create_s3(self, service_id, version, s3):
        if s3.response_condition == '':
            s3.response_condition = None;
        response = self._request('/service/%s/version/%s/logging/s3' % (service_id, version), 'POST', s3)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating s3 for for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def create_scalyr(self, service_id, version, scalyr):
        if scalyr.response_condition == '':
            scalyr.response_condition = None;
        response = self._request('/service/%s/version/%s/logging/scalyr' % (service_id, version), 'POST', scalyr)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating scalyr for for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def create_request_setting(self, service_id, version, request_setting):
        if request_setting.request_condition == '':
            request_setting.request_condition = None;
        response = self._request('/service/%s/version/%s/request_settings' % (service_id, version), 'POST', request_setting)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating request_setting for for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))


class FastlyStateEnforcerResult(object):
    def __init__(self, changed, actions, service):
        self.changed = changed
        self.actions = actions
        self.service = service


class FastlyStateEnforcer(object):
    def __init__(self, client):
        self.client = client

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
            self.deploy_version_with_settings(service.id, fastly_settings, activate_new_version)
            actions.append("Deployed new version because service has no active version")
        elif fastly_settings != current_version.settings:
            self.deploy_version_with_settings(service.id, fastly_settings, activate_new_version)
            actions.append("Deployed new version because settings are not up to date")

        changed = len(actions) > 0
        service = self.client.get_service(service.id)
        return FastlyStateEnforcerResult(actions=actions, changed=changed, service=service)

    def deploy_version_with_settings(self, service_id, settings, activate_version):
        version = self.client.create_version(service_id)
        version_number = version['number']

        for domain in settings.domains:
            self.client.create_domain(service_id, version_number, domain)

        for condition in settings.conditions:
            self.client.create_condition(service_id, version_number, condition)

        for backend in settings.backends:
            self.client.create_backend(service_id, version_number, backend)

        for gzip in settings.gzips:
            self.client.create_gzip(service_id, version_number, gzip)

        for header in settings.headers:
            self.client.create_header(service_id, version_number, header)

        for response_object in settings.response_objects:
            self.client.create_response_object(service_id, version_number, response_object)

        for vcl in settings.vcls:
            self.client.create_vcl(service_id, version_number, vcl)

        for s3 in settings.s3s:
            self.client.create_s3(service_id, version_number, s3)

        for scalyr in settings.scalyrs:
            self.client.create_scalyr(service_id, version_number, scalyr)

        for request_setting in settings.request_settings:
            self.client.create_request_setting(service_id, version_number, request_setting)

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
                backends=dict(default=None, required=True, type='list'),
                conditions=dict(default=None, required=False, type='list'),
                gzips=dict(default=None, required=False, type='list'),
                headers=dict(default=None, required=False, type='list'),
                response_objects=dict(default=None, required=False, type='list'),
                vcls=dict(default=None, required=False, type='list'),
                s3s=dict(default=None, required=False, type='list'),
                scalyrs=dict(default=None, required=False, type='list'),
                request_settings=dict(default=None, required=False, type='list'),
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
                'backends': self.module.params['backends'],
                'conditions': self.module.params['conditions'],
                'gzips': self.module.params['gzips'],
                'headers': self.module.params['headers'],
                'response_objects': self.module.params['response_objects'],
                'vcls': self.module.params['vcls'],
                's3s': self.module.params['s3s'],
                'scalyrs': self.module.params['scalyrs'],
                'request_settings': self.module.params['request_settings'],
            })
        except FastlyValidationError as err:
            self.module.fail_json(msg='Error in ' + err.cls + ': ' + err.message)
        except Exception as err:
            self.module.fail_json(msg=err.message)

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
            self.module.fail_json(msg=err.message)


def main():
    fastly_module = FastlyServiceModule()
    fastly_module.run()


if __name__ == '__main__':
    main()
