#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlyConfiguration

class TestFastlyGzip(TestCommon):

    GZIP_NAME = 'gzip-config-name'

    @TestCommon.vcr.use_cassette()
    def test_fastly_gzip(self):
        gzip_configuration = self.minimal_configuration.copy()
        gzip_configuration.update({
            'gzips': [{
                'name': self.GZIP_NAME,
                'content_types': 'text/html text/css application/javascript',
                'extensions': 'html css js'
            }]
        })

        configuration = FastlyConfiguration(gzip_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.configuration.gzips[0].name, self.GZIP_NAME)
        self.assertEqual(service.active_version.configuration, configuration)

if __name__ == '__main__':
    unittest.main()
