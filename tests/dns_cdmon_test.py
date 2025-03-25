import unittest
from unittest import mock
from certbot import errors
from certbot_dns_cdmon.dns_cdmon import Authenticator

class AuthenticatorTest(unittest.TestCase):
    def setUp(self):
        self.config = mock.MagicMock(
            cdmon_credentials='/fake/credentials.ini',
            cdmon_propagation_seconds=0
        )
        
        self.auth = Authenticator(self.config, "cdmon")
        self.auth.credentials = mock.MagicMock()
        self.auth.credentials.conf.side_effect = lambda key: {
            'api_key': 'test_api_key_123',
            'domain': 'example.com'
        }[key]

        self.success_response = mock.MagicMock()
        self.success_response.status_code = 200
        self.success_response.json.return_value = {'status': 'success'}

    def _mock_api_call(self, status_code=200, response_data=None):
        mock_response = mock.MagicMock()
        mock_response.status_code = status_code
        mock_response.json.return_value = response_data or {}
        return mock_response

    def test_subdomain_extraction(self):
        test_cases = [
            ('_acme-challenge.example.com', ''),
            ('_acme-challenge.sub.example.com', 'sub'),
            ('_acme-challenge.sub1.sub2.example.com', 'sub1.sub2'),
            ('example.com', ''),
            ('invalid.domain.com', '')
        ]
        
        for validation_name, expected in test_cases:
            with self.subTest(validation_name=validation_name):
                result = self.auth._get_cdmon_subdomain(validation_name)
                self.assertEqual(result, expected)

    @mock.patch('requests.post')
    def test_create_txt_record(self, mock_post):
        mock_post.side_effect = [
            self._mock_api_call(200, {'data': {'result': []}}),
            self.success_response
        ]
        
        self.auth._create_txt_record('test', 'validation_value')
        
        self.assertEqual(mock_post.call_count, 2)
        self.assertIn('getDnsRecords', mock_post.call_args_list[0][0][0])
        self.assertIn('dnsrecords/create', mock_post.call_args_list[1][0][0])

    @mock.patch('requests.post')
    def test_delete_txt_record(self, mock_post):
        mock_post.side_effect = [
            self._mock_api_call(200, {'data': {'result': [{'host': '_acme-challenge.test', 'type': 'TXT'}]}}),
            self.success_response
        ]
        
        self.auth._delete_txt_record('test', 'validation_value')
        
        self.assertEqual(mock_post.call_count, 2)
        self.assertIn('getDnsRecords', mock_post.call_args_list[0][0][0])
        self.assertIn('dnsrecords/delete', mock_post.call_args_list[1][0][0])

    @mock.patch('requests.post')
    def test_api_error_handling(self, mock_post):
        mock_post.return_value = self._mock_api_call(403, {'message': 'No API key found in request'})
        
        with self.assertRaises(errors.PluginError) as context:
            self.auth._create_txt_record('test', 'value')
        
        self.assertIn('CDmon API error: 403 - No API key found in request', str(context.exception))

    def test_invalid_credentials(self):
        self.auth.credentials.conf.side_effect = lambda key: {
            'api_key': '',
            'domain': 'example.com'
        }[key]

        with self.assertRaises(errors.PluginError) as context:
            self.auth._create_txt_record('test', 'value')
        
        self.assertIn('No API key found in request', str(context.exception))

    @mock.patch('requests.post')
    def test_cleanup_missing_record(self, mock_post):
        mock_post.return_value = self._mock_api_call(200, {'data': {'result': []}})
        
        self.auth._cleanup('example.com', 'test.example.com', 'validation')
        
        self.assertEqual(mock_post.call_count, 1)
        self.assertIn('getDnsRecords', mock_post.call_args_list[0][0][0])

    @mock.patch('requests.post')
    def test_special_characters(self, mock_post):
        mock_post.side_effect = [
            self._mock_api_call(200, {'data': {'result': []}}),
            self.success_response
        ]
        special_value = 'test"value!@# $%^&*()'
        
        self.auth._create_txt_record('test', special_value)
        
        create_call = mock_post.call_args_list[1]
        called_value = create_call[1]['json']['data']['value']
        self.assertEqual(called_value, f'"{special_value}"')

if __name__ == '__main__':
    unittest.main()