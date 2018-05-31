#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlyConfiguration

class TestFastlyLoggingSyslog(TestCommon):

    @TestCommon.vcr.use_cassette()
    def test_fastly_logging_syslog(self):
        logging_configuration = self.minimal_configuration.copy()
        logging_configuration.update({
            'syslogs': [{
                'name': 'test_syslog',
                'address': 'syslog.example.com',
                'port': 514,
                'use_tls': 0,
                'token': '[abc 123]',
                'format': '%h %l %u %t "%r" %>s %b',
            }],
        })

        configuration = FastlyConfiguration(logging_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service

        svc_conf = service.active_version.configuration

        self.assertEqual(svc_conf.syslogs[0].hostname, 'syslog.example.com'),
        self.assertEqual(svc_conf.syslogs[0].response_condition, None),
        self.assertEqual(svc_conf.syslogs[0].address, 'syslog.example.com'),
        self.assertEqual(svc_conf.syslogs[0].message_type, 'classic'),
        self.assertEqual(svc_conf.syslogs[0].name, 'test_syslog'),
        self.assertEqual(svc_conf.syslogs[0].port, 514),
        self.assertEqual(svc_conf.syslogs[0].use_tls, 0),
        self.assertEqual(svc_conf.syslogs[0].token, '[abc 123]'),
        self.assertEqual(svc_conf.syslogs[0].format, '%h %l %u %t "%r" %>s %b'),

        self.assertEqual(svc_conf, configuration)

        active_version_number = service.active_version.number
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.number, active_version_number)

    @TestCommon.vcr.use_cassette()
    def test_fastly_logging_syslog_remove(self):
        logging_configuration = self.minimal_configuration.copy()
        logging_configuration.update({
            'syslogs': [{
                'name': 'test_syslog',
                'address': 'syslog.example.com',
                'port': 514,
            }],
        })
        configuration = FastlyConfiguration(logging_configuration)

        # Configure with logging
        self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service

        # Now apply a configuration without logging
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, FastlyConfiguration(self.minimal_configuration.copy())).service
        svc_conf = service.active_version.configuration

        self.assertEqual(svc_conf.syslogs, [])


if __name__ == '__main__':
    unittest.main()

