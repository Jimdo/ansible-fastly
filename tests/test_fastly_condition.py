#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlySettings

class TestFastlyCondition(TestCommon):

    CONDITION_NAME = 'condition-name'

    @TestCommon.vcr.use_cassette()
    def test_fastly_condition(self):
        condition_settings = self.minimal_settings.copy()
        condition_settings.update({
            'conditions': [{
                'name': self.CONDITION_NAME,
                'priority': 0,
                'statement': 'req.url ~ "^/robots.txt"',
                'type': 'REQUEST'
            }]
        })

        settings = FastlySettings(condition_settings)
        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, settings).service
        self.assertEqual(service.active_version.settings.conditions[0].name, self.CONDITION_NAME)
        self.assertEqual(service.active_version.settings, settings)

if __name__ == '__main__':
    unittest.main()
