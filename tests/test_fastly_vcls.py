#!/usr/bin/env python
import os
import unittest
import sys

from test_common import TestCommon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'library'))
from fastly_service import FastlyConfiguration

class TestFastlyVclSnippets(TestCommon):

    VCLS_NAME = 'Main.vcl';
    
    @TestCommon.vcr.use_cassette()
    def test_fastly_vcl_main(self):
        content = '''
            sub vcl_recv {
            #FASTLY recv
            
              if (req.method != "HEAD" && req.method != "GET" && req.method != "FASTLYPURGE") {
                return(pass);
              }
            
              return(lookup);
            }
            
            sub vcl_fetch {
            #FASTLY fetch
            
              if ((beresp.status == 500 || beresp.status == 503) && req.restarts < 1 && (req.method == "GET" || req.method == "HEAD")) {
                restart;
              }
            
              if (req.restarts > 0) {
                set beresp.http.Fastly-Restarts = req.restarts;
              }
            
              if (beresp.http.Set-Cookie) {
                set req.http.Fastly-Cachetype = "SETCOOKIE";
                return(pass);
              }
            
              if (beresp.http.Cache-Control ~ "private") {
                set req.http.Fastly-Cachetype = "PRIVATE";
                return(pass);
              }
            
              if (beresp.status == 500 || beresp.status == 503) {
                set req.http.Fastly-Cachetype = "ERROR";
                set beresp.ttl = 1s;
                set beresp.grace = 5s;
                return(deliver);
              }
            
              if (beresp.http.Expires || beresp.http.Surrogate-Control ~ "max-age" || beresp.http.Cache-Control ~ "(s-maxage|max-age)") {
                # keep the ttl here
              } else {
                # apply the default ttl
                set beresp.ttl = 3600s;
              }
            
              return(deliver);
            }
            
            sub vcl_hit {
            #FASTLY hit
            
              if (!obj.cacheable) {
                return(pass);
              }
              return(deliver);
            }
            
            sub vcl_miss {
            #FASTLY miss
              return(fetch);
            }
            
            sub vcl_deliver {
            #FASTLY deliver
              return(deliver);
            }
            
            sub vcl_error {
            #FASTLY error
            }
            
            sub vcl_pass {
            #FASTLY pass
            }
            
            sub vcl_log {
            #FASTLY log
            }
        '''

        vcls_configuration = self.minimal_configuration.copy()
        vcls_configuration.update({
            'snippets': [{
                'name': self.VCLS_NAME,
                'dynamic': 0,
                'type': 'deliver',
                'content': content,
            }]
        })

        configuration = FastlyConfiguration(vcls_configuration)
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service

        self.assertEqual(service.active_version.configuration.vcls[0].name, self.VCLS_NAME)
        self.assertEqual(service.active_version.configuration.vcls[0].dynamic, 0)
        self.assertEqual(service.active_version.configuration.vcls[0].type, 'deliver')
        self.assertEqual(service.active_version.configuration.vcls[0].content, content)
        self.assertEqual(service.active_version.configuration, configuration)

        active_version_number = service.active_version.number
        service = self.enforcer.apply_configuration(self.FASTLY_TEST_SERVICE, configuration).service
        self.assertEqual(service.active_version.number, active_version_number)

if __name__ == '__main__':
    unittest.main()

