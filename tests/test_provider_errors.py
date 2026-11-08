import io
import json
import unittest
import urllib.error
from unittest.mock import patch, MagicMock
from promo_finder.providers import ChatProvider, http_error_message


def error(status, body):
    return urllib.error.HTTPError('https://example.com/api', status, 'failure', {}, io.BytesIO(body.encode()))


class ErrorDiagnosticsTests(unittest.TestCase):
    def test_model_permissions_are_specific_without_echoing_secret_message(self):
        for code, expected in [('model_permission_blocked_org','organization'),('model_permission_blocked_project','project')]:
            result=http_error_message(error(403,json.dumps({'error':{'code':code,'message':'SECRET script and key'}})))
            self.assertIn(expected,result)
            self.assertNotIn('SECRET',result)

    def test_gateway_signature_is_distinct_from_auth(self):
        result=http_error_message(error(403,'error code: 1010'))
        self.assertIn('gateway',result)
        self.assertIn('1010',result)

    def test_unknown_error_does_not_leak_any_provider_content(self):
        for body in ['SECRET', '<html>SECRET</html>', '{"error":{"code":"SECRET","message":"SECRET"}}', '[]']:
            self.assertNotIn('SECRET',http_error_message(error(403,body)))

    def test_auth_and_rate_limits_are_distinct(self):
        self.assertIn('Authentication failed',http_error_message(error(401,'')))
        self.assertIn('Rate limit',http_error_message(error(429,'')))

    def test_named_api_client_and_safe_error_reach_caller(self):
        opener=MagicMock()
        opener.open.side_effect=error(403,'error code: 1010')
        with patch('promo_finder.providers.urllib.request.build_opener',return_value=opener):
            with self.assertRaisesRegex(RuntimeError,'1010'):
                ChatProvider('https://example.com/api','test',api_key='SECRET').complete('system',{'synthetic':'data'})
        request=opener.open.call_args.args[0]
        self.assertTrue(request.get_header('User-agent').startswith('PromoScout/'))
        self.assertEqual(request.get_header('Accept'),'application/json')


if __name__=='__main__': unittest.main()
