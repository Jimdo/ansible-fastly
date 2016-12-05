#!/usr/bin/env python
import os
import unittest
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlyClient, FastlyStateEnforcer, FastlySettings, FastlyValidationError
import vcr

my_vcr = vcr.VCR(
        filter_headers = ['Fastly-Key'],
        cassette_library_dir = 'tests/fixtures/cassettes',
        record_mode='once',
)

class TestFastly(unittest.TestCase):

    FASTLY_TEST_SERVICE = 'Jimdo Fastly Ansible Module Test'
    FASTLY_TEST_DOMAIN = 'cdn.example7000.com'

    enforcer = None
    client = None

    settings_fixture = {
        'domains': [{
            'name': FASTLY_TEST_DOMAIN,
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

    @my_vcr.use_cassette()
    def setUp(self):
        if self.enforcer is None:
            if 'FASTLY_API_KEY' not in os.environ:
                raise RuntimeError('Error: FASTLY_API_KEY not set in environment!')

            self.client = FastlyClient(os.environ['FASTLY_API_KEY'])
            self.enforcer = FastlyStateEnforcer(self.client)

    @my_vcr.use_cassette()
    def tearDown(self):
        self.client.delete_service(self.FASTLY_TEST_SERVICE)

    # Given 'Service {name} does not exist'
    # Then 'Service {name} should be created'
    # Then 'A new version with settings to be applied should be created'
    # And 'The new version should be activated'
    @my_vcr.use_cassette()
    def test_service_does_not_exist(self):
        self.client.delete_service(self.FASTLY_TEST_SERVICE)

        test_settings = FastlySettings(self.settings_fixture)

        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, test_settings).service
        self.assertTrue(service.active_version.active)
        self.assertEqual(service.active_version.settings.response_objects, test_settings.response_objects)

    # Given 'Service {name} does not exist'
    # And 'activate_new_version is disabled'
    # Then 'Service {name} should be created'
    # Then 'A new version with settings to be applied should be created'
    # And 'The new version should not be activated'
    @my_vcr.use_cassette()
    def test_service_does_not_exist_and_activate_new_version_is_disabled(self):
        self.client.delete_service(self.FASTLY_TEST_SERVICE)

        test_settings = FastlySettings(self.settings_fixture)

        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, test_settings, False).service
        self.assertFalse(service.latest_version.active)
        self.assertEqual(service.latest_version.settings.response_objects, test_settings.response_objects)

    # Given 'Service {name} already exists'
    # And 'Settings of active version are different from settings to be applied'
    # Then 'A new version with settings to be applied should be created'
    # And 'The new version should be activated'
    @my_vcr.use_cassette()
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
    # And 'activate_new_version is disabled'
    # And 'Settings of current version are different from settings to be applied'
    # Then 'A new version with settings to be applied should be created'
    # And 'The new version should not be activated'
    @my_vcr.use_cassette()
    def test_service_does_exist_and_activate_new_version_is_disabled(self):
        new_settings = self.settings_fixture.copy()
        new_settings.update({
            'response_objects': [{
                'name': 'Set 301 status code',
                'status': 301
            }]
        })

        old_settings = FastlySettings(self.settings_fixture)
        new_settings = FastlySettings(new_settings)

        old_service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, old_settings, False).service
        new_service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, new_settings, False).service

        self.assertNotEqual(new_service.latest_version.settings.response_objects, old_settings.response_objects)
        self.assertNotEqual(old_service.latest_version.number, new_service.latest_version.number)

        self.assertFalse(new_service.latest_version.active)


    # Given 'Service {name} already exists'
    # And 'Settings of active version are equal to settings to be applied'
    # Then 'Nothing should happen'
    @my_vcr.use_cassette()
    def test_service_does_exist_and_settings_are_equal(self):
        new_settings = self.settings_fixture.copy()

        old_settings = FastlySettings(self.settings_fixture)
        new_settings = FastlySettings(new_settings)

        old_service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, old_settings).service
        new_service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, new_settings).service

        self.assertEqual(old_service.active_version.number, new_service.active_version.number)

    # Given 'Service {name} already exists'
    # And 'activate_new_version is disabled'
    # And 'Settings of current version are equal to settings to be applied'
    # Then 'Nothing should happen'
    @my_vcr.use_cassette()
    def test_service_does_exist_and_settings_are_equal_and_activate_new_version_is_disabled(self):
        new_settings = self.settings_fixture.copy()

        old_settings = FastlySettings(self.settings_fixture)
        new_settings = FastlySettings(new_settings)

        old_service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, old_settings, False).service
        new_service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, new_settings, False).service

        self.assertEqual(old_service.latest_version.number, new_service.latest_version.number)

    @my_vcr.use_cassette()
    def test_fastly_settings_normalization(self):
        settings = FastlySettings(self.settings_fixture)
        self.assertEqual(settings.response_objects[0].status, '302')
        self.assertNotEqual(settings.response_objects[0].status, 302)

    @my_vcr.use_cassette()
    def test_fastly_settings_validation(self):
        new_settings = self.settings_fixture.copy()
        new_settings.update({
            'response_objects': [{
                'status': 302
            }]
        })

        with self.assertRaises(FastlyValidationError):
            FastlySettings(new_settings)

    @my_vcr.use_cassette()
    def test_fastly_domain_comment_not_required(self):
        settings =  FastlySettings({
            'domains': [{
                'name': self.FASTLY_TEST_DOMAIN,
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
        })
        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, settings).service
        self.assertEqual(service.active_version.settings, settings)

    @my_vcr.use_cassette()
    def test_fastly_backend_port_not_required(self):
        settings =  FastlySettings({
            'domains': [{
                'name': self.FASTLY_TEST_DOMAIN,
            }],
            'backends': [{
                'name': 'localhost',
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
        })
        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, settings).service
        self.assertEqual(service.active_version.settings, settings)

    @my_vcr.use_cassette()
    def test_fastly_backend_empty_ssl_ca_cert(self):
        settings =  FastlySettings({
            'domains': [{
                'name': self.FASTLY_TEST_DOMAIN,
            }],
            'backends': [{
                'name': 'my-backend.example.net',
                'address': 'my-backend.example.net',
                'ssl_hostname': 'my-backend.example.net',
                'ssl_ca_cert': ''
            }]
        })
        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, settings).service
        self.assertEqual(service.active_version.settings, settings)

    @my_vcr.use_cassette()
    def test_fastly_header_priority_not_required(self):
        settings =  FastlySettings({
            'domains': [{
                'name': self.FASTLY_TEST_DOMAIN,
            }],
            'backends': [{
                'name': 'localhost',
                'address': '127.0.0.1'
            }],
            'headers': [{
                'name': 'Set Location header',
                'dst': 'http.Location',
                'type': 'response',
                'action': 'set',
                'src': '"https://u.jimcdn.com" req.url.path',
                'ignore_if_set': False
            }],
            'response_objects': [{
                'name': 'Set 302 status code',
                'status': 302
            }]
        })
        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, settings).service
        self.assertEqual(service.active_version.settings, settings)

    @my_vcr.use_cassette()
    def test_fastly_header_ignore_if_set_not_required(self):
        settings =  FastlySettings({
            'domains': [{
                'name': self.FASTLY_TEST_DOMAIN,
            }],
            'backends': [{
                'name': 'localhost',
                'address': '127.0.0.1'
            }],
            'headers': [{
                'name': 'Set Location header',
                'dst': 'http.Location',
                'type': 'response',
                'action': 'set',
                'src': '"https://u.jimcdn.com" req.url.path',
            }],
            'response_objects': [{
                'name': 'Set 302 status code',
                'status': 302
            }]
        })
        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, settings).service
        self.assertEqual(service.active_version.settings, settings)

    @my_vcr.use_cassette()
    def test_fastly_header_type_required(self):
        with self.assertRaises(FastlyValidationError):
            FastlySettings({
                'domains': [{
                    'name': self.FASTLY_TEST_DOMAIN,
                }],
                'backends': [{
                    'name': 'localhost',
                    'address': '127.0.0.1'
                }],
                'headers': [{
                    'name': 'Set Location header',
                    'dst': 'http.Location',
                    'action': 'set',
                    'src': '"https://u.jimcdn.com" req.url.path',
                }],
                'response_objects': [{
                    'name': 'Set 302 status code',
                    'status': 302
                }]
            })

    @my_vcr.use_cassette()
    def test_fastly_header_action_not_required(self):
        settings =  FastlySettings({
            'domains': [{
                'name': self.FASTLY_TEST_DOMAIN,
            }],
            'backends': [{
                'name': 'localhost',
                'address': '127.0.0.1'
            }],
            'headers': [{
                'name': 'Set Location header',
                'dst': 'http.Location',
                'type': 'response',
                'src': '"https://u.jimcdn.com" req.url.path',
            }],
            'response_objects': [{
                'name': 'Set 302 status code',
                'status': 302
            }]
        })
        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, settings).service
        self.assertEqual(service.active_version.settings, settings)

    @my_vcr.use_cassette()
    def test_fastly_response_object_status_not_required(self):
        settings =  FastlySettings({
            'domains': [{
                'name': self.FASTLY_TEST_DOMAIN,
            }],
            'backends': [{
                'name': 'localhost',
                'address': '127.0.0.1'
            }],
            'headers': [{
                'name': 'Set Location header',
                'dst': 'http.Location',
                'type': 'response',
                'src': '"https://u.jimcdn.com" req.url.path',
            }],
            'response_objects': [{
                'name': 'Set 200 status code',
            }]
        })
        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, settings).service
        self.assertEqual(service.active_version.settings, settings)

if __name__ == '__main__':
    unittest.main()

#######################################################


# Given 'Service {name} does exist'
# AND 'Service state is absent'
# Then 'Service {name} should be deleted'

# Given 'Service {name} does not exist'
# AND 'Service state is absent'
# Then 'Nothing should happen'
