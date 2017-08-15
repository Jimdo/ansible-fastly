#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlyConfiguration

class TestFastlyVclSnippets(TestCommon):

    VCL_SNIPPETS_NAME = 'Deliver stale content';
    
    @TestCommon.vcr.use_cassette()
    def test_fastly_vcl_snippets_deliver_stale_content(self):
        content = '''
            if (resp.status >= 500 && resp.status < 600) {
                if (stale.exists) {
                    restart;
                }
            }
        '''

        vcl_snippets_configuration = self.minimal_configuration.copy()
        vcl_snippets_configuration.update({
            'snippets': [{
                'name': self.VCL_SNIPPETS_NAME,
                'dynamic': 0,
                'type': 'deliver',
                'content': content,
            }]
        })

        configuration = FastlyConfiguration(vcl_snippets_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service

        self.assertEqual(service.active_version.configuration.snippets[0].name, self.VCL_SNIPPETS_NAME)
        self.assertEqual(service.active_version.configuration.snippets[0].dynamic, 0)
        self.assertEqual(service.active_version.configuration.snippets[0].type, 'deliver')
        self.assertEqual(service.active_version.configuration.snippets[0].content, content)
        self.assertEqual(service.active_version.configuration, configuration)

        active_version_number = service.active_version.number
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.number, active_version_number)

if __name__ == '__main__':
    unittest.main()

