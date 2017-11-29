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
    directors:
        required: false
        description:
            - List of directors
    gzips:
        required: false
        description:
            - List of gzip configurations
    headers:
        required: false
        description:
            - List of headers to manipulate for each request
    healthchecks:
        required: false
        description:
            - List of healthchecks to manipulate for each request
    request_settings:
        required: false
        description:
            - List of request settings
    response_objects:
        required: false
        description:
            - List of response objects
    vcl_snippets:
        required: false
        description:
            - List of VCL snippets
    upload_vcls:
        required: false
        description:
            - Upload VCL
    settings:
        required: false
        description:
            - Handles default settings for a service.
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
    vcl_snippets
      - name: Deliver stale content
        dynamic: 0
        type: deliver
        content: >
            if (resp.status >= 500 && resp.status < 600) {
                if (stale.exists) {
                    restart;
                }
            }
        priority: 110
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
'''

import httplib
import urllib
import json
import os

from ansible.module_utils.basic import *  # noqa: F403


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
        exclude_empty_str = self.schema[param_name].get('exclude_empty_str', False)

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
                value = int(value) if value is not None else default
            except ValueError:
                raise FastlyValidationError(self.__class__.__name__,
                                            "Field '%s' with value '%s' couldn't be converted to integer" % (
                                                param_name, value))
        elif param_type == 'bool':
            try:
                value = bool(value)
            except ValueError:
                raise FastlyValidationError(self.__class__.__name__,
                                            "Field '%s' with value '%s' couldn't be converted to boolean" % (
                                                param_name, value))
        elif param_type == 'list':
            if not isinstance(value, list):
                raise FastlyValidationError(self.__class__.__name__,
                                            "Field '%s' with value '%s' is not a list" % (
                                                param_name, value))

        if exclude_empty_str and value == "":
            value = None

        return value

    def __eq__(self, other):
        return self.__dict__ == other.__dict__


class FastlyDomain(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'comment': dict(required=False, type='str', default='')
    }

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.comment = self.read_config(config, validate_choices, 'comment')

    def sort_key(f):
        return f.name


class FastlyBackend(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'port': dict(required=False, type='int', default=80),
        'address': dict(required=True, type='str', default=None),
        'request_condition': dict(required=False, type='str', default=''),
        'ssl_hostname': dict(required=False, type='str', default=None),
        'ssl_ca_cert': dict(required=False, type='str', default=None, exclude_empty_str=True),
        'ssl_cert_hostname': dict(required=False, type='str', default=None, exclude_empty_str=True),
        'shield': dict(required=False, type='str', default=None, exclude_empty_str=True),
        'healthcheck': dict(required=False, type='str', default=None, exclude_empty_str=True),
        'weight': dict(required=False, type='int', default=100),
        'connect_timeout': dict(required=False, type='int', default=1000),
        'first_byte_timeout': dict(required=False, type='int', default=15000),
        'between_bytes_timeout': dict(required=False, type='int', default=10000),
        'error_threshold': dict(required=False, type='int', default=0),
        'max_conn': dict(required=False, type='int', default=200),
    }

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.port = self.read_config(config, validate_choices, 'port')
        self.address = self.read_config(config, validate_choices, 'address')
        self.request_condition = self.read_config(config, validate_choices, 'request_condition')
        self.ssl_hostname = self.read_config(config, validate_choices, 'ssl_hostname')
        self.ssl_ca_cert = self.read_config(config, validate_choices, 'ssl_ca_cert')
        self.ssl_cert_hostname = self.read_config(config, validate_choices, 'ssl_cert_hostname')
        self.shield = self.read_config(config, validate_choices, 'shield')
        self.healthcheck = self.read_config(config, validate_choices, 'healthcheck')
        self.weight = self.read_config(config, validate_choices, 'weight')
        self.connect_timeout = self.read_config(config, validate_choices, 'connect_timeout')
        self.first_byte_timeout = self.read_config(config, validate_choices, 'first_byte_timeout')
        self.between_bytes_timeout = self.read_config(config, validate_choices, 'between_bytes_timeout')
        self.error_threshold = self.read_config(config, validate_choices, 'error_threshold')
        self.max_conn = self.read_config(config, validate_choices, 'max_conn')

    def sort_key(f):
        return f.name


class FastlyCacheSettings(FastlyObject):
    schema = {
        'name': dict(required=True, type='str'),
        'action': dict(required=False, type='str', default=None, choices=['cache', 'pass', 'restart', None]),
        'cache_condition': dict(required=False, type='str', default=''),
        'stale_ttl': dict(required=False, type='int', default=0)
    }

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.action = self.read_config(config, validate_choices, 'action')
        self.cache_condition = self.read_config(config, validate_choices, 'cache_condition')
        self.stale_ttl = self.read_config(config, validate_choices, 'stale_ttl')

    def sort_key(f):
        return f.name


class FastlyCondition(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'comment': dict(required=False, type='str', default=''),
        'priority': dict(required=False, type='intstr', default='0'),
        'statement': dict(required=True, type='str'),
        'type': dict(required=True, type='str', default=None,
                     choices=['REQUEST', 'PREFETCH', 'CACHE', 'RESPONSE']),
    }

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.comment = self.read_config(config, validate_choices, 'comment')
        self.priority = self.read_config(config, validate_choices, 'priority')
        self.statement = self.read_config(config, validate_choices, 'statement')
        self.type = self.read_config(config, validate_choices, 'type')

    def sort_key(f):
        return f.name


class FastlyDirector(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'backends': dict(required=False, type='list', default=None),
        'capacity': dict(required=False, type='int', default=100),
        'comment': dict(required=False, type='str', default=''),
        'quorum': dict(required=False, type='int', default=75),
        'shield': dict(required=False, type='str', default=None),
        'type': dict(required=False, type='int', default=1),
        'retries': dict(required=False, type='int', default=5)
    }

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.backends = self.read_config(config, validate_choices, 'backends')
        self.capacity = self.read_config(config, validate_choices, 'capacity')
        self.comment = self.read_config(config, validate_choices, 'comment')
        self.quorum = self.read_config(config, validate_choices, 'quorum')
        self.shield = self.read_config(config, validate_choices, 'shield')
        self.type = self.read_config(config, validate_choices, 'type')
        self.retries = self.read_config(config, validate_choices, 'retries')

    def sort_key(f):
        return f.name


class FastlyGzip(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'cache_condition': dict(required=False, type='str', default=''),
        'content_types': dict(required=False, type='str', default=''),
        'extensions': dict(required=False, type='str', default=''),
    }

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.cache_condition = self.read_config(config, validate_choices, 'cache_condition')
        self.content_types = self.read_config(config, validate_choices, 'content_types')
        self.extensions = self.read_config(config, validate_choices, 'extensions')

    def sort_key(f):
        return f.name


class FastlyHeader(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'action': dict(required=False, type='str', default='set',
                       choices=['set', 'append', 'delete', 'regex', 'regex_repeat']),
        'dst': dict(required=True, type='str', default=None),
        'ignore_if_set': dict(required=False, type='intstr', default='0'),
        'priority': dict(required=False, type='intstr', default='100'),
        'regex': dict(required=False, type='str', default=''),
        'request_condition': dict(required=False, type='str', default=None),
        'response_condition': dict(required=False, type='str', default=None),
        'cache_condition': dict(required=False, type='str', default=None),
        'src': dict(required=True, type='str', default=None),
        'substitution': dict(required=False, type='str', default=''),
        'type': dict(required=True, type='str', default=None,
                     choices=['request', 'fetch', 'cache', 'response'])
    }

    def __init__(self, config, validate_choices):
        self.action = self.read_config(config, validate_choices, 'action')
        self.dst = self.read_config(config, validate_choices, 'dst')
        self.ignore_if_set = self.read_config(config, validate_choices, 'ignore_if_set')
        self.name = self.read_config(config, validate_choices, 'name')
        self.priority = self.read_config(config, validate_choices, 'priority')
        self.regex = self.read_config(config, validate_choices, 'regex')
        self.request_condition = self.read_config(config, validate_choices, 'request_condition')
        self.response_condition = self.read_config(config, validate_choices, 'response_condition')
        self.cache_condition = self.read_config(config, validate_choices, 'cache_condition')
        self.src = self.read_config(config, validate_choices, 'src')
        self.substitution = self.read_config(config, validate_choices, 'substitution')
        self.type = self.read_config(config, validate_choices, 'type')

    def sort_key(f):
        return f.name


class FastlyHealthcheck(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'check_interval': dict(required=False, type='int', default=None),
        'comment': dict(required=False, type='str', default=''),
        'expected_response': dict(required=False, type='int', default=200),
        'host': dict(required=True, type='str', default=None),
        'http_version': dict(required=False, type='str', default='1.1'),
        'initial': dict(required=False, type='int', default=None),
        'method': dict(required=False, type='str', default='HEAD'),
        'path': dict(required=False, type='str', default='/'),
        'threshold': dict(required=False, type='int', default=None),
        'timeout': dict(required=False, type='int', default=None),
        'window': dict(required=False, type='int', default=None),
    }

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.check_interval = self.read_config(config, validate_choices, 'check_interval')
        self.comment = self.read_config(config, validate_choices, 'comment')
        self.expected_response = self.read_config(config, validate_choices, 'expected_response')
        self.host = self.read_config(config, validate_choices, 'host')
        self.http_version = self.read_config(config, validate_choices, 'http_version')
        self.initial = self.read_config(config, validate_choices, 'initial')
        self.method = self.read_config(config, validate_choices, 'method')
        self.path = self.read_config(config, validate_choices, 'path')
        self.threshold = self.read_config(config, validate_choices, 'threshold')
        self.timeout = self.read_config(config, validate_choices, 'timeout')
        self.window = self.read_config(config, validate_choices, 'window')

    def sort_key(f):
        return f.name


class FastlyRequestSetting(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'request_condition': dict(required=False, type='str', default=''),
        'force_miss': dict(required=False, type='int', default=0),
        'force_ssl': dict(required=False, type='int', default=0),
        'action': dict(required=False, type='str', default=None, choices=['lookup', 'pass', None]),
        'bypass_busy_wait': dict(required=False, type='int', default=0),
        'max_stale_age': dict(required=False, type='int', default=0),
        'hash_keys': dict(required=False, type='str', default=''),
        'xff': dict(required=False, type='str', default=None, choices=['clear', 'leave', 'append', 'append_all', 'overwrite', None]),
        'timer_support': dict(required=False, type='int', default=0),
        'geo_headers': dict(required=False, type='int', default=0),
        'default_host': dict(required=False, type='str', default='')
    }

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.request_condition = self.read_config(config, validate_choices, 'request_condition')
        self.force_miss = self.read_config(config, validate_choices, 'force_miss')
        self.force_ssl = self.read_config(config, validate_choices, 'force_ssl')
        self.action = self.read_config(config, validate_choices, 'action')
        self.bypass_busy_wait = self.read_config(config, validate_choices, 'bypass_busy_wait')
        self.max_stale_age = self.read_config(config, validate_choices, 'max_stale_age')
        self.hash_keys = self.read_config(config, validate_choices, 'hash_keys')
        self.xff = self.read_config(config, validate_choices, 'xff')
        self.timer_support = self.read_config(config, validate_choices, 'timer_support')
        self.geo_headers = self.read_config(config, validate_choices, 'geo_headers')
        self.default_host = self.read_config(config, validate_choices, 'default_host')

    def sort_key(f):
        return f.name


class FastlyResponseObject(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'request_condition': dict(required=False, type='str', default=''),
        'response': dict(required=False, type='str', default='Ok'),
        'status': dict(required=False, type='intstr', default='200'),
        'content': dict(required=False, type='str', default=''),
        'content_type': dict(required=False, type='str', default='')
    }

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.request_condition = self.read_config(config, validate_choices, 'request_condition')
        self.response = self.read_config(config, validate_choices, 'response')
        self.status = self.read_config(config, validate_choices, 'status')
        self.content = self.read_config(config, validate_choices, 'content')
        self.content_type = self.read_config(config, validate_choices, 'content_type')

    def sort_key(f):
        return f.name


class FastlyVclUpload(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'content': dict(required=True, type='str', default=None)
    }

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.content = self.read_config(config, validate_choices, 'content')

    def sort_key(f):
        return f.name


class FastlyVclSnippet(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'dynamic': dict(required=False, type='int', default=0),
        'type': dict(required=False, type='str', default='init'),
        'content': dict(required=True, type='str', default=None),
        'priority': dict(required=False, type='int', default=100)
    }

    def __init__(self, config, validate_choices):
        self.name = self.read_config(config, validate_choices, 'name')
        self.dynamic = self.read_config(config, validate_choices, 'dynamic')
        self.type = self.read_config(config, validate_choices, 'type')
        self.content = self.read_config(config, validate_choices, 'content')
        self.priority = self.read_config(config, validate_choices, 'priority')

    def sort_key(f):
        return f.name


class FastlySettings(FastlyObject):
    schema = {
        'general.default_ttl': dict(required=False, type='int', default=3600)
    }

    def __init__(self, config, validate_choices):
        self.general_default_ttl = self.read_config(config, validate_choices, 'general.default_ttl')

    def to_json(self):
        return {
            'general.default_ttl': self.general_default_ttl
        }


class FastlyConfiguration(object):
    def __init__(self, configuration, validate_choices=True):
        self.domains = []
        self.healthchecks = []
        self.backends = []
        self.cache_settings = []
        self.conditions = []
        self.directors = []
        self.gzips = []
        self.headers = []
        self.response_objects = []
        self.request_settings = []
        self.uploads = []
        self.snippets = []
        self.settings = FastlySettings(dict(), validate_choices)

        if 'domains' in configuration and configuration['domains'] is not None:
            for domain in configuration['domains']:
                self.domains.append(FastlyDomain(domain, validate_choices))

        if 'healthchecks' in configuration and configuration['healthchecks'] is not None:
            for healthcheck in configuration['healthchecks']:
                self.healthchecks.append(FastlyHealthcheck(healthcheck, validate_choices))

        if 'backends' in configuration and configuration['backends'] is not None:
            for backend in configuration['backends']:
                self.backends.append(FastlyBackend(backend, validate_choices))

        if 'cache_settings' in configuration and configuration['cache_settings'] is not None:
            for cache_settings in configuration['cache_settings']:
                self.cache_settings.append(FastlyCacheSettings(cache_settings, validate_choices))

        if 'conditions' in configuration and configuration['conditions'] is not None:
            for condition in configuration['conditions']:
                self.conditions.append(FastlyCondition(condition, validate_choices))

        if 'directors' in configuration and configuration['directors'] is not None:
            for director in configuration['directors']:
                self.directors.append(FastlyDirector(director, validate_choices))

        if 'gzips' in configuration and configuration['gzips'] is not None:
            for gzip in configuration['gzips']:
                self.gzips.append(FastlyGzip(gzip, validate_choices))

        if 'headers' in configuration and configuration['headers'] is not None:
            for header in configuration['headers']:
                self.headers.append(FastlyHeader(header, validate_choices))

        if 'request_settings' in configuration and configuration['request_settings'] is not None:
            for request_setting in configuration['request_settings']:
                self.request_settings.append(FastlyRequestSetting(request_setting, validate_choices))

        if 'response_objects' in configuration and configuration['response_objects'] is not None:
            for response_object in configuration['response_objects']:
                self.response_objects.append(FastlyResponseObject(response_object, validate_choices))

        if 'uploads' in configuration and configuration['uploads'] is not None:
            for upload in configuration['uploads']:
                self.uploads.append(FastlyVclUpload(upload, validate_choices))

        if 'snippets' in configuration and configuration['snippets'] is not None:
            for snippet in configuration['snippets']:
                self.snippets.append(FastlyVclSnippet(snippet, validate_choices))

        if 'settings' in configuration and configuration['settings'] is not None:
            self.settings = FastlySettings(configuration['settings'], validate_choices)

    def __eq__(self, other):
        return sorted(self.domains, key=FastlyDomain.sort_key) == sorted(other.domains, key=FastlyDomain.sort_key) \
            and sorted(self.healthchecks, key=FastlyHealthcheck.sort_key) == sorted(other.healthchecks, key=FastlyHealthcheck.sort_key) \
            and sorted(self.backends, key=FastlyBackend.sort_key) == sorted(other.backends, key=FastlyBackend.sort_key) \
            and sorted(self.cache_settings, key=FastlyCacheSettings.sort_key) == sorted(other.cache_settings, key=FastlyCacheSettings.sort_key) \
            and sorted(self.conditions, key=FastlyCondition.sort_key) == sorted(other.conditions, key=FastlyCondition.sort_key) \
            and sorted(self.directors, key=FastlyDirector.sort_key) == sorted(other.directors, key=FastlyDirector.sort_key) \
            and sorted(self.gzips, key=FastlyGzip.sort_key) == sorted(other.gzips, key=FastlyGzip.sort_key) \
            and sorted(self.headers, key=FastlyHeader.sort_key) == sorted(other.headers, key=FastlyHeader.sort_key) \
            and sorted(self.request_settings, key=FastlyRequestSetting.sort_key) == sorted(other.request_settings, key=FastlyRequestSetting.sort_key) \
            and sorted(self.response_objects, key=FastlyResponseObject.sort_key) == sorted(other.response_objects, key=FastlyResponseObject.sort_key) \
            and sorted(self.uploads, key=FastlyVclUpload.sort_key) == sorted(other.uploads, key=FastlyVclUpload.sort_key) \
            and sorted(self.snippets, key=FastlyVclSnippet.sort_key) == sorted(other.snippets, key=FastlyVclSnippet.sort_key) \
            and self.settings == other.settings

    def __ne__(self, other):
        return not self.__eq__(other)


class FastlyVersion(object):
    def __init__(self, version_configuration):
        self.configuration = FastlyConfiguration(version_configuration, False)
        self.number = version_configuration['number']
        self.active = version_configuration['active']


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
            raise Exception("Error creating service with name '%s': %s" % (service_name, response.payload['detail']))

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
            raise Exception("Error creating domain for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def create_healthcheck(self, service_id, version, healthcheck):
        response = self._request('/service/%s/version/%s/healthcheck' % (service_id, version), 'POST', healthcheck)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating healthcheck for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def create_backend(self, service_id, version, backend):
        response = self._request('/service/%s/version/%s/backend' % (service_id, version), 'POST', backend)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating backend for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def create_director(self, service_id, version, director):
        response = self._request('/service/%s/version/%s/director' % (service_id, version), 'POST', director)
        if response.status != 200:
            raise Exception("Error creating director for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

        payload = response.payload
        if director.backends is not None:
            for backend in director.backends:
                response = self._request('/service/%s/version/%s/director/%s/backend/%s' % (service_id, version, director.name, backend), 'POST')
                if response.status != 200:
                    raise Exception("Error establishing a relationship between director %s and backend %s,  service %s, version %s (%s)" % (
                        director.name, backend, service_id, version, response.payload['detail']))
        return payload

    def create_cache_settings(self, service_id, version, cache_settings):
        response = self._request('/service/%s/version/%s/cache_settings' % (service_id, version), 'POST', cache_settings)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating cache_settings for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def create_condition(self, service_id, version, condition):
        response = self._request('/service/%s/version/%s/condition' % (service_id, version), 'POST', condition)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating condition for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def create_gzip(self, service_id, version, gzip):
        response = self._request('/service/%s/version/%s/gzip' % (service_id, version), 'POST',
                                 gzip)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating gzip for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def create_header(self, service_id, version, header):
        response = self._request('/service/%s/version/%s/header' % (service_id, version), 'POST', header)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating header for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def create_request_setting(self, service_id, version, request_setting):
        response = self._request('/service/%s/version/%s/request_settings' % (service_id, version), 'POST',
                                 request_setting)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating request setting for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def create_response_object(self, service_id, version, response_object):
        response = self._request('/service/%s/version/%s/response_object' % (service_id, version), 'POST',
                                 response_object)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating response object for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))

    def upload_custom_vcl(self, service_id, version, upload_vcl):
        response = self._request('/service/%s/version/%s/vcl' % (service_id, version), 'POST', upload_vcl)

        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error uploading VCL '%s' for service %s, version %s (%s)" % (upload_vcl['name'], service_id, version, response.payload['detail']))        

    def create_vcl_snippet(self, service_id, version, vcl_snippet):
        response = self._request('/service/%s/version/%s/snippet' % (service_id, version), 'POST', vcl_snippet)

        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating VCL snippet '%s' for service %s, version %s (%s)" % (vcl_snippet['name'], service_id, version, response.payload['detail']))

    def create_settings(self, service_id, version, settings):
        response = self._request('/service/%s/version/%s/settings' % (service_id, version), 'PUT', settings)
        if response.status == 200:
            return response.payload
        else:
            raise Exception("Error creating settings for service %s, version %s (%s)" % (
                service_id, version, response.payload['detail']))


class FastlyStateEnforcerResult(object):
    def __init__(self, changed, actions, service):
        self.changed = changed
        self.actions = actions
        self.service = service


class FastlyStateEnforcer(object):
    def __init__(self, client):
        self.client = client

    def apply_configuration(self, service_name, fastly_configuration, activate_new_version=True):

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
            self.deploy_version_with_configuration(service.id, fastly_configuration, activate_new_version)
            actions.append("Deployed new version because service has no active version")
        elif fastly_configuration != current_version.configuration:
            self.deploy_version_with_configuration(service.id, fastly_configuration, activate_new_version)
            actions.append("Deployed new version because settings are not up to date")

        changed = len(actions) > 0
        service = self.client.get_service(service.id)
        return FastlyStateEnforcerResult(actions=actions, changed=changed, service=service)

    def deploy_version_with_configuration(self, service_id, configuration, activate_version):
        version = self.client.create_version(service_id)
        version_number = version['number']

        for domain in configuration.domains:
            self.client.create_domain(service_id, version_number, domain)

        # create healthchecks before backends
        for healthcheck in configuration.healthchecks:
            self.client.create_healthcheck(service_id, version_number, healthcheck)

        # create conditions before dependencies (e.g. cache_settings)
        for condition in configuration.conditions:
            self.client.create_condition(service_id, version_number, condition)

        for backend in configuration.backends:
            self.client.create_backend(service_id, version_number, backend)

        # director should follow after backends
        for director in configuration.directors:
            self.client.create_director(service_id, version_number, director)

        for cache_settings in configuration.cache_settings:
            self.client.create_cache_settings(service_id, version_number, cache_settings)

        for gzip in configuration.gzips:
            self.client.create_gzip(service_id, version_number, gzip)

        for header in configuration.headers:
            self.client.create_header(service_id, version_number, header)

        for request_setting in configuration.request_settings:
            self.client.create_request_setting(service_id, version_number, request_setting)

        for response_object in configuration.response_objects:
            self.client.create_response_object(service_id, version_number, response_object)

        for upload_vcl in configuration.uploads:
            self.client.upload_custom_vcl(service_id, version_number, upload_vcl)

        for vcl_snippet in configuration.snippets:
            self.client.create_vcl_snippet(service_id, version_number, vcl_snippet)

        if configuration.settings:
            self.client.create_settings(service_id, version_number, configuration.settings)

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
        self.module = AnsibleModule(  # noqa: F405
            argument_spec=dict(
                state=dict(default='present', choices=['present', 'absent'], type='str'),
                fastly_api_key=dict(no_log=True, type='str'),
                name=dict(required=True, type='str'),
                activate_new_version=dict(required=False, type='bool', default=True),
                healthchecks=dict(default=None, required=False, type='list'),
                domains=dict(default=None, required=True, type='list'),
                backends=dict(default=None, required=True, type='list'),
                cache_settings=dict(default=None, required=False, type='list'),
                conditions=dict(default=None, required=False, type='list'),
                directors=dict(default=None, required=False, type='list'),
                gzips=dict(default=None, required=False, type='list'),
                headers=dict(default=None, required=False, type='list'),
                request_settings=dict(default=None, required=False, type='list'),
                response_objects=dict(default=None, required=False, type='list'),
                upload_vcls=dict(default=None, required=False, type='list'),
                vcl_snippets=dict(default=None, required=False, type='list'),
                settings=dict(default=None, required=False, type='dict'),
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

    def configuration(self):
        try:
            return FastlyConfiguration({
                'domains': self.module.params['domains'],
                'healthchecks': self.module.params['healthchecks'],
                'backends': self.module.params['backends'],
                'cache_settings': self.module.params['cache_settings'],
                'conditions': self.module.params['conditions'],
                'directors': self.module.params['directors'],
                'gzips': self.module.params['gzips'],
                'headers': self.module.params['headers'],
                'request_settings': self.module.params['request_settings'],
                'response_objects': self.module.params['response_objects'],
                'uploads': self.module.params['upload_vcls'],
                'snippets': self.module.params['vcl_snippets'],
                'settings': self.module.params['settings']
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
                result = enforcer.apply_configuration(service_name, self.configuration(), activate_new_version)
                self.module.exit_json(changed=result.changed, service_id=result.service.id, actions=result.actions)

        except Exception as err:
            self.module.fail_json(msg=err.message)


def main():
    fastly_module = FastlyServiceModule()
    fastly_module.run()


if __name__ == '__main__':
    main()
