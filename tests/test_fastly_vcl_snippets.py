#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlyConfiguration

class TestFastlyVclSnippets(TestCommon):

    VCL_SNIPPETS_NAMES = [
        'Deliver stale content',
        'Conditionally deactivate stale_while_revalidate',
        'Fetch for serving stale content',
        'Handle 503 errors'
    ]
    
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
                'name': self.VCL_SNIPPETS_NAMES[0],
                'dynamic': 0,
                'type': 'deliver',
                'content': content,
            }]
        })

        configuration = FastlyConfiguration(vcl_snippets_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service

        self.assertEqual(service.active_version.configuration.snippets[0].name, self.VCL_SNIPPETS_NAMES[0])
        self.assertEqual(service.active_version.configuration.snippets[0].dynamic, 0)
        self.assertEqual(service.active_version.configuration.snippets[0].type, 'deliver')
        self.assertEqual(service.active_version.configuration.snippets[0].content, content)
        self.assertEqual(service.active_version.configuration, configuration)

        active_version_number = service.active_version.number
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.number, active_version_number)
    
    @TestCommon.vcr.use_cassette()
    def test_fastly_vcl_snippets_deactivate_stale_while_revalidate(self):

        content = '''
            if (req.http.Fastly-FF) {
              set req.max_stale_while_revalidate = 0s;
            }
        '''

        vcl_snippets_configuration = self.minimal_configuration.copy()
        vcl_snippets_configuration.update({
            'snippets': [{
                'name': self.VCL_SNIPPETS_NAMES[1],
                'dynamic': 0,
                'type': 'recv',
                'content': content,
            }]
        })
        configuration = FastlyConfiguration(vcl_snippets_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service

        self.assertEqual(service.active_version.configuration.snippets[0].name, self.VCL_SNIPPETS_NAMES[1])
        self.assertEqual(service.active_version.configuration.snippets[0].dynamic, 0)
        self.assertEqual(service.active_version.configuration.snippets[0].type, 'recv')
        self.assertEqual(service.active_version.configuration.snippets[0].content, content)
        self.assertEqual(service.active_version.configuration, configuration)

        active_version_number = service.active_version.number
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.number, active_version_number)

    @TestCommon.vcr.use_cassette()
    def test_fastly_vcl_snippets_fetch_for_serving_stale_content(self):

        content = '''
            if (beresp.status >= 500 && beresp.status < 600) {
                if (stale.exists) {
                    return(deliver_stale);
                }

                if (req.restarts < 1 && (req.request == "GET" || req.request == "HEAD")) {
                    restart;
                }

                error 503;
            }

            set beresp.stale_if_error = 259200s;
            set beresp.stale_while_revalidate = 10s;
        '''

        vcl_snippets_configuration = self.minimal_configuration.copy()
        vcl_snippets_configuration.update({
            'snippets': [{
                'name': self.VCL_SNIPPETS_NAMES[2],
                'dynamic': 0,
                'type': 'fetch',
                'content': content,
            }]
        })
        configuration = FastlyConfiguration(vcl_snippets_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service

        self.assertEqual(service.active_version.configuration.snippets[0].name, self.VCL_SNIPPETS_NAMES[2])
        self.assertEqual(service.active_version.configuration.snippets[0].dynamic, 0)
        self.assertEqual(service.active_version.configuration.snippets[0].type, 'fetch')
        self.assertEqual(service.active_version.configuration.snippets[0].content, content)
        self.assertEqual(service.active_version.configuration, configuration)

        active_version_number = service.active_version.number
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.number, active_version_number)

    @TestCommon.vcr.use_cassette()
    def test_fastly_vcl_snippets_handle_errors(self):

        content = '''
            if (obj.status >= 500 && obj.status < 600) {
              if (stale.exists) {
                return(deliver_stale);
              }

              synthetic {"<!DOCTYPE html><html>Sorry. Coming back soon!.</html>"};
                return(deliver);
            }
        '''

        vcl_snippets_configuration = self.minimal_configuration.copy()
        vcl_snippets_configuration.update({
            'snippets': [{
                'name': self.VCL_SNIPPETS_NAMES[3],
                'dynamic': 0,
                'type': 'error',
                'content': content,
            }]
        })
        configuration = FastlyConfiguration(vcl_snippets_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service

        self.assertEqual(service.active_version.configuration.snippets[0].name, self.VCL_SNIPPETS_NAMES[3])
        self.assertEqual(service.active_version.configuration.snippets[0].dynamic, 0)
        self.assertEqual(service.active_version.configuration.snippets[0].type, 'error')
        self.assertEqual(service.active_version.configuration.snippets[0].content, content)
        self.assertEqual(service.active_version.configuration, configuration)

        active_version_number = service.active_version.number
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.number, active_version_number)

if __name__ == '__main__':
    unittest.main()

