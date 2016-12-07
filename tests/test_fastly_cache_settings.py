#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlyConfiguration

class TestFastlyCacheSettings(TestCommon):

    CACHE_SETTINGS_NAME = 'cache-settings-config-name'

    @TestCommon.vcr.use_cassette()
    def test_fastly_cache_settings(self):
        cache_settings_configuration = self.minimal_configuration.copy()
        cache_settings_configuration.update({
            'cache_settings': [{
                'name': self.CACHE_SETTINGS_NAME,
                'stale_ttl': 10
            }]
        })

        configuration = FastlyConfiguration(cache_settings_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.configuration.cache_settings[0].name, self.CACHE_SETTINGS_NAME)
        self.assertEqual(service.active_version.configuration.cache_settings[0].stale_ttl, 10)
        self.assertEqual(service.active_version.configuration, configuration)

        active_version_number = service.active_version.number
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.number, active_version_number)

    @TestCommon.vcr.use_cassette()
    def test_fastly_cache_settings_without_stale_ttl(self):
        cache_settings_configuration = self.minimal_configuration.copy()
        cache_settings_configuration.update({
            'cache_settings': [{
                'name': self.CACHE_SETTINGS_NAME
            }]
        })

        configuration = FastlyConfiguration(cache_settings_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.configuration.cache_settings[0].name, self.CACHE_SETTINGS_NAME)
        self.assertEqual(service.active_version.configuration.cache_settings[0].stale_ttl, 0)
        self.assertEqual(service.active_version.configuration, configuration)

        active_version_number = service.active_version.number
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.number, active_version_number)

    @TestCommon.vcr.use_cassette()
    def test_fastly_cache_settings_with_action(self):
        cache_settings_configuration = self.minimal_configuration.copy()
        cache_settings_configuration.update({
            'cache_settings': [{
                'name': self.CACHE_SETTINGS_NAME,
                'action': 'pass',
                'stale_ttl': 10
            }]
        })

        configuration = FastlyConfiguration(cache_settings_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.configuration.cache_settings[0].action, 'pass')
        self.assertEqual(service.active_version.configuration, configuration)

        active_version_number = service.active_version.number
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.number, active_version_number)

if __name__ == '__main__':
    unittest.main()
