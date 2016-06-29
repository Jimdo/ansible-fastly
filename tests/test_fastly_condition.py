#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlySettings

class TestFastlyCondition(TestCommon):

    CONDITION_NAME = 'gzip-config-name'

    # @TestCommon.vcr.use_cassette()
    def test_fastly_gzip(self):
        condition_settings = self.minimal_settings.copy()
        condition_settings.update({
            'conditions': [{
                'name': self.CONDITION_NAME,
                'type': 'request',
            }]
        })

        settings = FastlySettings(condition_settings)
        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, settings).service
        self.assertEqual(service.active_version.settings.conditions[0].name, self.CONDITION_NAME)
        self.assertEqual(service.active_version.settings, settings)

if __name__ == '__main__':
    unittest.main()

# comment	string	A comment.
# name	string	Name of the condition.
# priority	integer	Priority assigned to condition. Order executes from 1 to 10, with 1 being first and 10 being last.
# service_id	string	The alphanumeric string identifying a service.
# statement	string	The statement used to determine if the condition is met.
# type	string	Type of the condition, either "REQUEST" (req), "RESPONSE" (req, resp), or "CACHE" (req, beresp).
# version	integer	The current version of a service.