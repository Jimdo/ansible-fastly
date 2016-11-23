#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlySettings

class TestFastlyS3(TestCommon):

    S3_NAME = 's3-name'

    @TestCommon.vcr.use_cassette()
    def test_fastly_s3(self):
        s3_settings = self.minimal_settings.copy()
        s3_settings.update({
            's3s': [{
                'name': self.S3_NAME,
                'access_key': 'iam-key',
                'secret_key': 'iam-secret',
                'bucket_name': 's3-bucket',
                'path': '/my-app/',
                'period': 3600
            }]
        })
        settings = FastlySettings(s3_settings)
        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, settings).service
        self.assertEqual(service.active_version.settings.s3s[0].name, self.S3_NAME)
        self.assertEqual(service.active_version.settings, settings)

if __name__ == '__main__':
    unittest.main()
