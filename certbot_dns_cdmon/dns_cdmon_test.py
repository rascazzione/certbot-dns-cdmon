import unittest
from unittest import mock

from certbot_dns_cdmon.dns_cdmon import Authenticator

class AuthenticatorTest(unittest.TestCase):
    def setUp(self):
        # Configuración dummy para el test
        self.credential_path = '/dummy/path'
        self.config = mock.MagicMock(
            cdmon_credentials=self.credential_path,
            cdmon_propagation_seconds=0  # no esperar en los tests
        )
        self.auth = Authenticator(self.config, "cdmon")
        
        # Inicializamos las credenciales de prueba
        self.auth.credentials = mock.MagicMock()
        self.auth.credentials.conf.side_effect = lambda key: {
            'api_key': 'dummy',
            'domain': 'example.com'
        }[key]
    
    def test_perform(self):
        # Patch del método _create_txt_record para capturar la llamada
        self.auth._create_txt_record = mock.MagicMock()
        self.auth._perform('example.com', 'test.example.com', 'validation')
        # Con _get_cdmon_subdomain, 'test.example.com' se convierte en subdominio 'test'
        self.auth._create_txt_record.assert_called_once_with('test', 'validation')
    
    def test_cleanup(self):
        # Patch de _delete_dns_txt_record y simulamos que existe el registro TXT
        self.auth._delete_dns_txt_record = mock.MagicMock()
        self.auth._list_dns_records = mock.MagicMock(return_value={
            'data': {
                'result': [{
                    'type': 'TXT',
                    'host': '_acme-challenge.test'
                }]
            }
        })
        self.auth._cleanup('example.com', 'test.example.com', 'validation')
        # Verificamos que se invoque _delete_dns_txt_record con los parámetros correctos:
        # dominio: 'example.com', subdominio: '_acme-challenge.test', api_key: 'dummy'
        self.auth._delete_dns_txt_record.assert_called_once_with('example.com', '_acme-challenge.test', 'dummy')

if __name__ == "__main__":
    unittest.main()