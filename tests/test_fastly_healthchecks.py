#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlyConfiguration

class TestFastlyDirectors(TestCommon):

    @TestCommon.vcr.use_cassette()
    def test_fastly_healthchecks(self):
        healthcheck_configuration = self.minimal_configuration.copy()
        healthcheck_configuration.update({
            'healthchecks': [{
                'name'              : 'test_healthcheck',
                'host'              : self.FASTLY_TEST_DOMAIN,
                'method'            : 'GET',
                'path'              : '/healthcheck',
                'expected_response' : 200,
                # Fastly Medium setup:
                'threshold'         : 3,
                'window'            : 5,
                'initial'           : 4,
                'check_interval'    : 15000,
                'timeout'           : 5000,
            }],
        })

        healthcheck_configuration['backends'][0].update({
            'healthcheck' : 'test_healthcheck',
        })

        configuration = FastlyConfiguration(healthcheck_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service

        self.assertEqual(service.active_version.configuration.healthchecks[0].name, 'test_healthcheck')
        self.assertEqual(service.active_version.configuration.healthchecks[0].host, self.FASTLY_TEST_DOMAIN)
        self.assertEqual(service.active_version.configuration.healthchecks[0].method, 'GET')
        self.assertEqual(service.active_version.configuration.healthchecks[0].path, '/healthcheck')
        self.assertEqual(service.active_version.configuration.healthchecks[0].expected_response, 200)
        self.assertEqual(service.active_version.configuration.healthchecks[0].threshold, 3)
        self.assertEqual(service.active_version.configuration.healthchecks[0].window, 5)
        self.assertEqual(service.active_version.configuration.healthchecks[0].initial, 4)
        self.assertEqual(service.active_version.configuration.healthchecks[0].check_interval, 15000)
        self.assertEqual(service.active_version.configuration.healthchecks[0].timeout, 5000)
        self.assertEqual(service.active_version.configuration.backends[0].healthcheck, 'test_healthcheck')
        self.assertEqual(service.active_version.configuration, configuration)

        active_version_number = service.active_version.number
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.number, active_version_number)

if __name__ == '__main__':
    unittest.main()

