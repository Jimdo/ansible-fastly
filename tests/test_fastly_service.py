#!/usr/bin/env python
import os
import unittest
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlyClient, FastlyStateEnforcer, FastlySettings, FastlyValidationError

class TestFastly(unittest.TestCase):

    FASTLY_TEST_SERVICE = 'Jimdo Fastly Ansible Module Test'

    enforcer = None
    client = None

    settings_fixture = {
        'domains': [{
            'name': 'u.test.jimcdn2.com',
            'comment': 'test1'
        }],
        'backends': [{
            'name': 'localhost',
            'port': '80',
            'address': '127.0.0.1'
        }],
        'headers': [{
            'name': 'Set Location header',
            'dst': 'http.Location',
            'type': 'response',
            'action': 'set',
            'src': '"https://u.jimcdn.com" req.url.path',
            'ignore_if_set': False,
            'priority': 10
        }],
        'response_objects': [{
            'name': 'Set 302 status code',
            'status': 302
        }]
    }

    def setUp(self):
        if self.enforcer is None:
            if 'FASTLY_API_KEY' not in os.environ:
                raise RuntimeError('Error: FASTLY_API_KEY not set in environment!')

            self.client = FastlyClient(os.environ['FASTLY_API_KEY'])
            self.enforcer = FastlyStateEnforcer(self.client)

    def tearDown(self):
        self.client.delete_service(self.FASTLY_TEST_SERVICE)

    # Given 'Service {name} does not exist'
    # Then 'Service {name} should be created'
    # Then 'A new version with settings to be applied should be created'
    # And 'The new version should be activated'
    def test_service_does_not_exist(self):
        self.client.delete_service(self.FASTLY_TEST_SERVICE)

        test_settings = FastlySettings(self.settings_fixture)

        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, test_settings).service
        self.assertTrue(service.active_version.active)
        self.assertEqual(service.active_version.settings.response_objects, test_settings.response_objects)

    # Given 'Service {name} already exists'
    # And 'Settings of active version are different from settings to be applied'
    # Then 'A new version with settings to be applied should be created'
    # And 'The new version should be activated'
    def test_service_does_exist(self):
        new_settings = self.settings_fixture.copy()
        new_settings.update({
            'response_objects': [{
                'name': 'Set 301 status code',
                'status': 301
            }]
        })

        old_settings = FastlySettings(self.settings_fixture)
        new_settings = FastlySettings(new_settings)

        old_service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, old_settings).service
        new_service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, new_settings).service

        self.assertNotEqual(new_service.active_version.settings.response_objects, old_settings.response_objects)
        self.assertNotEqual(old_service.active_version.number, new_service.active_version.number)

        self.assertTrue(new_service.active_version.active)

    # Given 'Service {name} already exists'
    # And 'Settings of active version are equal to settings to be applied'
    # Then 'Nothing should happen'
    def test_service_does_exist_and_settings_are_equal(self):
        new_settings = self.settings_fixture.copy()

        old_settings = FastlySettings(self.settings_fixture)
        new_settings = FastlySettings(new_settings)

        old_service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, old_settings).service
        new_service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, new_settings).service

        self.assertEqual(old_service.active_version.number, new_service.active_version.number)

    def test_fastly_settings_normalization(self):
        settings = FastlySettings(self.settings_fixture)
        self.assertEqual(settings.response_objects[0].status, '302')
        self.assertNotEqual(settings.response_objects[0].status, 302)

    def test_fastly_settings_validation(self):
        new_settings = self.settings_fixture.copy()
        new_settings.update({
            'response_objects': [{
                'name': 'Set 302 status code'
            }]
        })

        with self.assertRaises(FastlyValidationError):
            FastlySettings(new_settings)


if __name__ == '__main__':
    unittest.main()

#######################################################


# Given 'Service {name} does exist'
# AND 'Service state is absent'
# Then 'Service {name} should be deleted'

# Given 'Service {name} does not exist'
# AND 'Service state is absent'
# Then 'Nothing should happen'
