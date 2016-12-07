#!/usr/bin/env python
import os
import unittest
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlyClient, FastlyStateEnforcer
import vcr

class TestCommon(unittest.TestCase):
    FASTLY_TEST_SERVICE = 'Fastly Ansible Module Test'
    FASTLY_TEST_DOMAIN = 'example7000.com'

    enforcer = None
    client = None

    vcr = vcr.VCR(
            filter_headers = ['Fastly-Key'],
            cassette_library_dir = 'tests/fixtures/cassettes',
            record_mode='once',
            func_path_generator=lambda x: x.__self__.__class__.__name__ + '_' + x.__name__,
            path_transformer=vcr.VCR.ensure_suffix('.yml'),
    )

    minimal_configuration = {
        'domains': [{
            'name': FASTLY_TEST_DOMAIN,
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
        }],
        'conditions': None,
        'gzips': None,
    }

    @vcr.use_cassette()
    def setUp(self):
        if self.enforcer is None:
            if 'FASTLY_API_KEY' not in os.environ:
                raise RuntimeError('Error: FASTLY_API_KEY not set in environment!')

            self.client = FastlyClient(os.environ['FASTLY_API_KEY'])
            self.enforcer = FastlyStateEnforcer(self.client)

    @vcr.use_cassette()
    def tearDown(self):
        self.client.delete_service(self.FASTLY_TEST_SERVICE)