#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlyConfiguration

class TestFastlySettings(TestCommon):
    @TestCommon.vcr.use_cassette()
    def test_fastly_settings(self):
        settings_configuration = self.minimal_configuration.copy()
        settings_configuration.update({
            'settings': {
                'general.default_ttl': 1000
            }
        })

        settings_configuration = FastlyConfiguration(settings_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, settings_configuration).service
        self.assertEqual(service.active_version.configuration.settings.general_default_ttl, 1000)
        self.assertEqual(service.active_version.configuration, settings_configuration)

        active_version_number = service.active_version.number
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, settings_configuration).service
        self.assertEqual(service.active_version.number, active_version_number)

if __name__ == '__main__':
    unittest.main()
