#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlySettings

class TestFastlyScalyr(TestCommon):

    SCALYR_NAME = 'scalyr-name'

    @TestCommon.vcr.use_cassette()
    def test_fastly_scalyr(self):
        scalyr_settings = self.minimal_settings.copy()
        scalyr_settings.update({
            'scalyrs': [{
                'name': self.SCALYR_NAME,
                'format': '%h %l %u %t "%r" %>s %b',
                'format_version': 1,
                'token': 'test'
            }]
        })
        settings = FastlySettings(scalyr_settings)
        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, settings).service
        self.assertEqual(service.active_version.settings.scalyrs[0].name, self.SCALYR_NAME)
        self.assertEqual(service.active_version.settings, settings)

if __name__ == '__main__':
    unittest.main()
