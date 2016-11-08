#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlySettings

class TestFastlyRequestSetting(TestCommon):

    REQUEST_SETTING_NAME = 'request-setting-name'

    @TestCommon.vcr.use_cassette()
    def test_fastly_request_setting(self):
        request_setting_settings = self.minimal_settings.copy()
        request_setting_settings.update({
            'request_settings': [{
                'name': self.REQUEST_SETTING_NAME,
                'force_ssl': 0,
                'xff': 'append_all'
            }]
        })
        settings = FastlySettings(request_setting_settings)
        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, settings).service
        self.assertEqual(service.active_version.settings.request_settings[0].name, self.REQUEST_SETTING_NAME)
        self.assertEqual(service.active_version.settings, settings)

if __name__ == '__main__':
    unittest.main()
