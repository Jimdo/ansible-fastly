#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlySettings

class TestFastlyVCL(TestCommon):

    VCL_NAME = 'vcl-name'

    @TestCommon.vcr.use_cassette()
    def test_fastly_vcl(self):
        vcl_settings = self.minimal_settings.copy()
        vcl_settings.update({
            'vcls': [{
                'name': self.VCL_NAME,
                'main': True,
                'content': 'sub vcl_hit { ' + "\n" +
                    '#FASTLY hit ' + "\n" +
                     'if (!obj.cacheable) { \
                       return(pass); \
                     } \
                     return(deliver); \
                    }'
            }]
        })
        settings = FastlySettings(vcl_settings)
        service = self.enforcer.apply_settings(self.FASTLY_TEST_SERVICE, settings).service
        self.assertEqual(service.active_version.settings.vcls[0].name, self.VCL_NAME)
        self.assertEqual(service.active_version.settings, settings)

if __name__ == '__main__':
    unittest.main()
