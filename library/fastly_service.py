#!/usr/bin/python
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
    headers:
        required: false
        description:
            - List of headers to manipulate for each request
    response_objects:
        required: false
        description:
            - List of response objects
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

    def to_json(self):
        return self.__dict__

    def read_config(self, config, param_name):
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

        if choices is not None and value not in choices:
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

    def __init__(self, config):
        self.name = self.read_config(config, 'name')
        self.comment = self.read_config(config, 'comment')


class FastlyBackend(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'port': dict(required=False, type='int', default=80),
        'address': dict(required=True, type='str', default=None)
    }

    def __init__(self, config):
        self.name = self.read_config(config, 'name')
        self.port = self.read_config(config, 'port')
        self.address = self.read_config(config, 'address')


class FastlyHeader(FastlyObject):
    schema = {
        'action': dict(required=False, type='str', default='set',
                       choices=['set', 'append', 'delete', 'regex', 'regex_repeat']),
        'name': dict(required=True, type='str', default=None),
        'dst': dict(required=True, type='str', default=None),
        'type': dict(required=True, type='str', default=None,
                     choices=['request', 'fetch', 'cache', 'response']),
        'src': dict(required=True, type='str', default=None),
        'ignore_if_set': dict(required=False, type='intstr', default='0'),
        'priority': dict(required=False, type='intstr', default='100')
    }

    def __init__(self, config):
        self.name = self.read_config(config, 'name')
        self.dst = self.read_config(config, 'dst')
        self.type = self.read_config(config, 'type')
        self.action = self.read_config(config, 'action')
        self.src = self.read_config(config, 'src')
        self.ignore_if_set = self.read_config(config, 'ignore_if_set')
        self.priority = self.read_config(config, 'priority')


class FastlyResponseObject(FastlyObject):
    schema = {
        'name': dict(required=True, type='str', default=None),
        'response': dict(required=False, type='str', default='Ok'),
        'status': dict(required=False, type='intstr', default='200')
    }

    def __init__(self, config):
        self.name = self.read_config(config, 'name')
        self.response = self.read_config(config, 'response')
        self.status = self.read_config(config, 'status')


class FastlySettings(object):
    def __init__(self, settings):
        self.domains = []
        self.backends = []
        self.headers = []
        self.response_objects = []

        if settings['domains']:
            for domain in settings['domains']:
                self.domains.append(FastlyDomain(domain))

        if settings['backends']:
            for backend in settings['backends']:
                self.backends.append(FastlyBackend(backend))

        if settings['headers']:
            for header in settings['headers']:
                self.headers.append(FastlyHeader(header))

        if settings['response_objects']:
            for response_object in settings['response_objects']:
                self.response_objects.append(FastlyResponseObject(response_object))

    def __eq__(self, other):
        return self.domains == other.domains \
               and self.backends == other.backends \
               and self.headers == other.headers \
               and self.response_objects == other.response_objects

    def __ne__(self, other):
        return not self.__eq__(other)


class FastlyVersion(object):
    def __init__(self, version_settings):
        self.settings = FastlySettings(version_settings)
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

        for backend in settings.backends:
            self.client.create_backend(service_id, version_number, backend)

        for header in settings.headers:
            self.client.create_header(service_id, version_number, header)

        for response_object in settings.response_objects:
            self.client.create_response_object(service_id, version_number, response_object)

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
                headers=dict(default=None, required=False, type='list'),
                response_objects=dict(default=None, required=False, type='list'),
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
                'headers': self.module.params['headers'],
                'response_objects': self.module.params['response_objects']
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
