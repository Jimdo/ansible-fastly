#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlyConfiguration

class TestFastlyCondition(TestCommon):

    CONDITION_NAME = 'condition-name'

    @TestCommon.vcr.use_cassette()
    def test_fastly_condition(self):
        condition_configuration = self.minimal_configuration.copy()
        condition_configuration.update({
            'conditions': [{
                'name': self.CONDITION_NAME,
                'priority': 0,
                'statement': 'req.url ~ "^/robots.txt"',
                'type': 'REQUEST'
            }]
        })

        configuration = FastlyConfiguration(condition_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.configuration.conditions[0].name, self.CONDITION_NAME)
        self.assertEqual(service.active_version.configuration, configuration)

if __name__ == '__main__':
    unittest.main()
