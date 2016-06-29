#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlySettings

class TestFastlyGzip(TestCommon):

    GZIP_NAME = 'gzip-config-name'

    @TestCommon.vcr.use_cassette()
    def test_fastly_gzip(self):
        gzip_settings = self.minimal_settings.copy()
        gzip_settings.update({
            'gzips': [{
                'name': self.GZIP_NAME,
                'content_types': 'text/html text/css application/javascript',
                'extensions': 'html css js'
            }]
        })

        settings = FastlySettings(gzip_settings)
        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, settings).service
        self.assertEqual(service.active_version.settings.gzips[0].name, self.GZIP_NAME)
        self.assertEqual(service.active_version.settings, settings)

if __name__ == '__main__':
    unittest.main()
