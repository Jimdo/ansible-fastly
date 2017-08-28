#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlyConfiguration

class TestFastlyDirectors(TestCommon):

    @TestCommon.vcr.use_cassette()
    def test_fastly_director_with_one_backend(self):
        director_configuration = self.minimal_configuration.copy()
        director_configuration.update({
            'directors': [{
                'name': 'client_director',
                'type': '4',
                'backends': ['localhost'],
            }]
        })

        configuration = FastlyConfiguration(director_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service

        self.assertEqual(service.active_version.configuration.directors[0].name, 'client_director')
        self.assertEqual(service.active_version.configuration.directors[0].type, 4)
        self.assertEqual(service.active_version.configuration.directors[0].backends[0], 'localhost')
        self.assertEqual(service.active_version.configuration, configuration)

        active_version_number = service.active_version.number
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.number, active_version_number)

if __name__ == '__main__':
    unittest.main()

