#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlyConfiguration

class TestFastlyResponseObject(TestCommon):

    @TestCommon.vcr.use_cassette()
    def test_fastly_response_object_defaults(self):
        healthcheck_configuration = self.minimal_configuration.copy()
        healthcheck_configuration.update({
            'response_objects': [{
                'name': 'Set 200 status code',
            }]
        })

        configuration = FastlyConfiguration(healthcheck_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service

        self.assertEqual(service.active_version.configuration.response_objects[0].name, 'Set 200 status code')
        self.assertEqual(service.active_version.configuration.response_objects[0].status, '200')
        self.assertEqual(service.active_version.configuration.response_objects[0].response, 'Ok')
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

