import unittest
from unittest import mock
import requests
import json

from certbot import errors
from certbot_dns_cdmon.dns_cdmon import Authenticator, ACME_CHALLENGE_PREFIX


class AuthenticatorTest(unittest.TestCase):
    """Test cases for CDmon DNS Authenticator."""

    def setUp(self):
        """Set up test fixtures."""
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
            'api_key': 'dummy_key',
            'domain': ''  # Dominio vacío para probar la detección automática
        }[key]
        
        # Mock del método _get_http_session para evitar llamadas reales
        self.auth._get_http_session = mock.MagicMock()
        self.session_mock = mock.MagicMock()
        self.auth._get_http_session.return_value = self.session_mock
        
        # Respuesta mock para las llamadas a la API
        self.response_mock = mock.MagicMock()
        self.response_mock.status_code = 200
        self.response_mock.json.return_value = {
            'data': {
                'result': []
            }
        }
        self.session_mock.post.return_value = self.response_mock
    
    def test_validate_credentials(self):
        """Test credential validation."""
        # Caso válido - solo API key es requerida ahora
        self.auth._validate_credentials()  # No debería lanzar excepción
        
        # Caso inválido - API key vacía
        self.auth.credentials.conf.side_effect = lambda key: {
            'api_key': '',
            'domain': ''
        }[key]
        with self.assertRaises(errors.PluginError):
            self.auth._validate_credentials()
        
        # Caso válido - dominio vacío pero API key presente
        self.auth.credentials.conf.side_effect = lambda key: {
            'api_key': 'dummy_key',
            'domain': ''
        }[key]
        self.auth._validate_credentials()  # No debería lanzar excepción
    
    def test_detect_base_domain(self):
        """Test automatic domain detection."""
        # Caso con dominio en credenciales
        self.auth.credentials.conf.side_effect = lambda key: {
            'api_key': 'dummy_key',
            'domain': 'example.com'
        }[key]
        
        domain = self.auth._detect_base_domain('example.com', 'test.example.com')
        self.assertEqual(domain, 'example.com')
        
        # Caso sin dominio en credenciales, detección automática
        self.auth.credentials.conf.side_effect = lambda key: {
            'api_key': 'dummy_key',
            'domain': ''
        }[key]
        
        # Limpiar el mapa de dominios para forzar la detección
        self.auth._domain_map = {}
        
        domain = self.auth._detect_base_domain('example.com', 'test.example.com')
        self.assertEqual(domain, 'example.com')
        
        # Caso con subdominio más complejo
        self.auth._domain_map = {}
        domain = self.auth._detect_base_domain('sub.example.com', 'test.sub.example.com')
        self.assertEqual(domain, 'sub.example.com')
        
        # Caso con nombre de validación que incluye _acme-challenge
        self.auth._domain_map = {}
        domain = self.auth._detect_base_domain('example.com', '_acme-challenge.example.com')
        self.assertEqual(domain, 'example.com')
    
    def test_get_base_domain_for_validation(self):
        """Test getting base domain for validation."""
        # Caso con dominio ya en el mapa
        self.auth._domain_map = {'test.example.com': 'example.com'}
        domain = self.auth._get_base_domain_for_validation('test.example.com')
        self.assertEqual(domain, 'example.com')
        
        # Caso con dominio en credenciales
        self.auth._domain_map = {}
        self.auth.credentials.conf.side_effect = lambda key: {
            'api_key': 'dummy_key',
            'domain': 'example.com'
        }[key]
        
        domain = self.auth._get_base_domain_for_validation('test.example.com')
        self.assertEqual(domain, 'example.com')
        
        # Caso sin dominio en credenciales ni en mapa
        self.auth._domain_map = {}
        self.auth.credentials.conf.side_effect = lambda key: {
            'api_key': 'dummy_key',
            'domain': ''
        }[key]
        
        with self.assertRaises(errors.PluginError):
            self.auth._get_base_domain_for_validation('test.example.com')
    
    def test_get_cdmon_subdomain(self):
        """Test subdomain extraction from validation name."""
        # Configurar un dominio base para la prueba
        self.auth._domain_map = {'test.example.com': 'example.com'}
        
        # Caso normal
        result = self.auth._get_cdmon_subdomain('test.example.com')
        self.assertEqual(result, 'test')
        
        # Caso con prefijo _acme-challenge
        result = self.auth._get_cdmon_subdomain('_acme-challenge.test.example.com')
        self.assertEqual(result, 'test')
        
        # Caso con _acme-challenge como subdominio completo
        result = self.auth._get_cdmon_subdomain('_acme-challenge.example.com')
        self.assertEqual(result, '')
        
        # Caso con dominio que no coincide
        self.auth._domain_map = {'test.otherdomain.com': 'otherdomain.com'}
        result = self.auth._get_cdmon_subdomain('test.example.com')
        self.assertEqual(result, '')
    
    def test_format_acme_subdomain(self):
        """Test formatting of ACME challenge subdomain."""
        # Caso con subdominio
        result = self.auth._format_acme_subdomain('test')
        self.assertEqual(result, f'{ACME_CHALLENGE_PREFIX}.test')
        
        # Caso sin subdominio
        result = self.auth._format_acme_subdomain('')
        self.assertEqual(result, ACME_CHALLENGE_PREFIX)
    
    def test_perform(self):
        """Test perform method with domain detection."""
        # Configurar mocks
        self.auth._detect_base_domain = mock.MagicMock(return_value='example.com')
        self.auth._get_cdmon_subdomain = mock.MagicMock(return_value='test')
        self.auth._create_txt_record = mock.MagicMock()
        
        # Ejecutar perform
        self.auth._perform('example.com', 'test.example.com', 'validation')
        
        # Verificar que se llamó a detect_base_domain
        self.auth._detect_base_domain.assert_called_once_with('example.com', 'test.example.com')
        
        # Verificar que se llamó a get_cdmon_subdomain
        self.auth._get_cdmon_subdomain.assert_called_once_with('test.example.com')
        
        # Verificar que se llamó a create_txt_record con los parámetros correctos
        self.auth._create_txt_record.assert_called_once_with('test', 'validation', 'test.example.com')
        
        # Probar manejo de errores
        self.auth._create_txt_record.side_effect = Exception("Test error")
        with self.assertRaises(errors.PluginError):
            self.auth._perform('example.com', 'test.example.com', 'validation')
    
    def test_cleanup(self):
        """Test cleanup method with domain detection."""
        # Configurar mocks
        self.auth._get_cdmon_subdomain = mock.MagicMock(return_value='test')
        self.auth._delete_txt_record = mock.MagicMock()
        
        # Ejecutar cleanup
        self.auth._cleanup('example.com', 'test.example.com', 'validation')
        
        # Verificar que se llamó a get_cdmon_subdomain
        self.auth._get_cdmon_subdomain.assert_called_once_with('test.example.com')
        
        # Verificar que se llamó a delete_txt_record con los parámetros correctos
        self.auth._delete_txt_record.assert_called_once_with('test', 'validation', 'test.example.com')
        
        # Probar manejo de errores
        self.auth._delete_txt_record.side_effect = Exception("Test error")
        with self.assertRaises(errors.PluginError):
            self.auth._cleanup('example.com', 'test.example.com', 'validation')
    
    def test_create_txt_record(self):
        """Test creating TXT record with domain detection."""
        # Configurar mocks
        self.auth._get_base_domain_for_validation = mock.MagicMock(return_value='example.com')
        self.auth._find_txt_records = mock.MagicMock(return_value=[])
        self.auth._create_dns_txt_record = mock.MagicMock()
        
        # Ejecutar create_txt_record
        self.auth._create_txt_record('test', 'validation', 'test.example.com')
        
        # Verificar que se llamó a get_base_domain_for_validation
        self.auth._get_base_domain_for_validation.assert_called_once_with('test.example.com')
        
        # Verificar que se llamó a create_dns_txt_record
        self.auth._create_dns_txt_record.assert_called_once()
        
        # Caso con registro existente
        self.auth._find_txt_records.return_value = [{'type': 'TXT', 'host': f'{ACME_CHALLENGE_PREFIX}.test'}]
        self.auth._edit_dns_txt_record = mock.MagicMock()
        
        # Ejecutar create_txt_record de nuevo
        self.auth._create_txt_record('test', 'validation', 'test.example.com')
        
        # Verificar que se llamó a edit_dns_txt_record
        self.auth._edit_dns_txt_record.assert_called_once()
    
    def test_delete_txt_record(self):
        """Test deleting TXT record with domain detection."""
        # Configurar mocks
        self.auth._get_base_domain_for_validation = mock.MagicMock(return_value='example.com')
        self.auth._find_txt_records = mock.MagicMock(return_value=[
            {'type': 'TXT', 'host': f'{ACME_CHALLENGE_PREFIX}.test'}
        ])
        self.auth._delete_dns_txt_record = mock.MagicMock()
        
        # Ejecutar delete_txt_record
        self.auth._delete_txt_record('test', 'validation', 'test.example.com')
        
        # Verificar que se llamó a get_base_domain_for_validation
        self.auth._get_base_domain_for_validation.assert_called_once_with('test.example.com')
        
        # Verificar que se llamó a delete_dns_txt_record
        self.auth._delete_dns_txt_record.assert_called_once()
        
        # Caso sin registro existente
        self.auth._find_txt_records.return_value = []
        self.auth._delete_dns_txt_record.reset_mock()
        
        # Ejecutar delete_txt_record de nuevo
        self.auth._delete_txt_record('test', 'validation', 'test.example.com')
        
        # Verificar que no se llamó a delete_dns_txt_record
        self.auth._delete_dns_txt_record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
