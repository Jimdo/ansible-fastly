#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlyConfiguration

class TestFastlyS3s(TestCommon):

    @TestCommon.vcr.use_cassette()
    def test_fastly_s3s(self):
        s3s_configuration = self.minimal_configuration.copy()
        s3s_configuration.update({
            's3s': [{
                'name'              : 'test_s3',
                'domain'            : self.FASTLY_TEST_DOMAIN,
                'secret_key'        : 'SECRET',
                'period'            : 60,
                'bucket_name'       : 'prod-fastly-logs',
                'timestamp_format'  : '%Y-%m-%dT%H:%M:%S.000',
                'redundancy'        : 'standard',
                'access_key'        : 'ACCESS_KEY',
                'format'            : '%{%Y-%m-%dT%H:%S.000}t %h "%r" %>s %b',
            }],
        })

        configuration = FastlyConfiguration(s3s_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service

        svc_conf = service.active_version.configuration

        self.assertEqual(svc_conf.s3s[0].name, 'test_s3')
        self.assertEqual(svc_conf.s3s[0].domain, self.FASTLY_TEST_DOMAIN)
        self.assertEqual(svc_conf.s3s[0].secret_key, 'SECRET')
        self.assertEqual(svc_conf.s3s[0].period, 60)
        self.assertEqual(svc_conf.s3s[0].bucket_name, 'prod-fastly-logs')
        self.assertEqual(svc_conf.s3s[0].timestamp_format, '%Y-%m-%dT%H:%M:%S.000')
        self.assertEqual(svc_conf.s3s[0].redundancy, 'standard')
        self.assertEqual(svc_conf.s3s[0].access_key, 'ACCESS_KEY')
        self.assertEqual(svc_conf.s3s[0].format, '%{%Y-%m-%dT%H:%S.000}t %h "%r" %>s %b')
        self.assertEqual(svc_conf, configuration)

        active_version_number = service.active_version.number
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.number, active_version_number)

if __name__ == '__main__':
    unittest.main()

