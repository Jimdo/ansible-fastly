#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlySettings

class TestFastlySettings(TestCommon):
    @TestCommon.vcr.use_cassette()
    def test_fastly_settings(self):
        settings = self.minimal_settings.copy()
        settings.update({
            'settings': {
                'general.default_ttl': 1000
            }
        })

        settings = FastlySettings(settings)
        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, settings).service
        self.assertEqual(service.active_version.settings.settings.general_default_ttl, 1000)
        self.assertEqual(service.active_version.settings, settings)

        active_version_number = service.active_version.number
        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, settings).service
        self.assertEqual(service.active_version.number, active_version_number)

if __name__ == '__main__':
    unittest.main()
