#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlySettings

class TestFastlyGzip(TestCommon):

    @TestCommon.vcr.use_cassette()
    def test_fastly_gzip(self):
        gzip_settings = self.minimal_settings.copy()
        gzip_settings.update({
            'gzip': [{
                'name': 'gzip-config-name',
                'content_types': 'text/html text/css application/javascript',
                'extensions': 'html css js'
            }]
        })

        settings = FastlySettings(gzip_settings)
        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, settings).service
        self.assertEqual(service.active_version.settings, settings)

if __name__ == '__main__':
    unittest.main()
