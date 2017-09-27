#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlyConfiguration

class TestFastlyRequestSetting(TestCommon):

    REQUEST_SETTING_NAME = 'request-setting-config-name'

    @TestCommon.vcr.use_cassette()
    def test_fastly_request_setting_defaults(self):
        request_setting_configuration = self.minimal_configuration.copy()
        request_setting_configuration.update({
            'request_settings': [{
                'name': self.REQUEST_SETTING_NAME,
                'action': 'pass',
                'xff': 'append',
                'hash_keys': 'req.url,req.http.host,req.http.Fastly-SSL',
                'max_stale_age': 30,
                'force_miss': 1,
                'force_ssl': 1,
                'timer_support': 1,
                'geo_headers': 1,
                'bypass_busy_wait': 1,
                'default_host': 'example.net',
            }]
        })

        configuration = FastlyConfiguration(request_setting_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service

        self.assertEqual(service.active_version.configuration.request_settings[0].name, self.REQUEST_SETTING_NAME)
        self.assertEqual(service.active_version.configuration.request_settings[0].action, 'pass')
        self.assertEqual(service.active_version.configuration.request_settings[0].xff, 'append')
        self.assertEqual(service.active_version.configuration.request_settings[0].hash_keys, 'req.url,req.http.host,req.http.Fastly-SSL')
        self.assertEqual(service.active_version.configuration.request_settings[0].max_stale_age, 30)
        self.assertEqual(service.active_version.configuration.request_settings[0].force_miss, 1)
        self.assertEqual(service.active_version.configuration.request_settings[0].force_ssl, 1)
        self.assertEqual(service.active_version.configuration.request_settings[0].timer_support, 1)
        self.assertEqual(service.active_version.configuration.request_settings[0].geo_headers, 1)
        self.assertEqual(service.active_version.configuration.request_settings[0].bypass_busy_wait, 1)
        self.assertEqual(service.active_version.configuration.request_settings[0].default_host, 'example.net')
        self.assertEqual(service.active_version.configuration, configuration)

        active_version_number = service.active_version.number
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.number, active_version_number)


    @TestCommon.vcr.use_cassette()
    def test_fastly_response_object_content_content_type(self):
        healthcheck_configuration = self.minimal_configuration.copy()
        healthcheck_configuration.update({
            'response_objects': [{
                'name': 'Set 200 status code',
                'status': 200,
                'response': 'Ok',
                'content': 'Hello from Fastly',
                'content_type': 'text/plain',
            }]
        })

        configuration = FastlyConfiguration(healthcheck_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service

        self.assertEqual(service.active_version.configuration.response_objects[0].name, 'Set 200 status code')
        self.assertEqual(service.active_version.configuration.response_objects[0].status, '200')
        self.assertEqual(service.active_version.configuration.response_objects[0].response, 'Ok')
        self.assertEqual(service.active_version.configuration.response_objects[0].content, 'Hello from Fastly')
        self.assertEqual(service.active_version.configuration.response_objects[0].content_type, 'text/plain')
        self.assertEqual(service.active_version.configuration, configuration)

        active_version_number = service.active_version.number
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.number, active_version_number)

if __name__ == '__main__':
    unittest.main()

