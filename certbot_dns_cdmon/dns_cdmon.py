"""CDmon DNS Authenticator."""
import json
import logging
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from certbot import errors
from certbot.plugins import dns_common
from certbot.plugins.dns_common import CredentialsConfiguration

# Configuración avanzada de logging
logger = logging.getLogger(__name__)

# Constantes para mejorar la legibilidad y mantenimiento
ACME_CHALLENGE_PREFIX = "_acme-challenge"
DEFAULT_TTL = 60
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 0.5
RETRY_STATUS_FORCELIST = [429, 500, 502, 503, 504]
API_BASE_URL = "https://api-domains.cdmon.services/api-domains"


class Authenticator(dns_common.DNSAuthenticator):
    """DNS Authenticator for CDmon

    This Authenticator uses the CDmon API to fulfill a dns-01 challenge.
    """

    description = "Obtain certificates using a DNS TXT record (via CDmon API)"

    def __init__(self, *args, **kwargs):
        """Initialize the authenticator with default values."""
        super(Authenticator, self).__init__(*args, **kwargs)
        self.credentials = None
        self._session = None
        self._domain_map = {}  # Mapeo de nombres de validación a dominios base
        logger.debug("Inicializando autenticador CDmon DNS")

    @classmethod
    def add_parser_arguments(cls, add):
        """Add command line arguments to the CLI parser.

        Args:
            add: Function that adds arguments to the parser.
        """
        super(Authenticator, cls).add_parser_arguments(
            add, default_propagation_seconds=90
        )
        add("credentials", help="CDmon API credentials INI file.")
        logger.debug("Argumentos del parser añadidos")

    def more_info(self):
        """Return information about this plugin.

        Returns:
            str: A description string about the plugin.
        """
        return (
            "This plugin configures a DNS TXT record to respond to a dns-01 "
            "challenge using the CDmon API."
        )

    def _setup_credentials(self):
        """Set up the credentials needed for the CDmon API."""
        logger.debug("Configurando credenciales para la API de CDmon")
        self.credentials = self._configure_credentials(
            "credentials",
            "CDmon API credentials INI file",
            {
                "api_key": "API key for CDmon API",
                # El dominio ahora es opcional
                "domain": "Base domain managed by CDmon (optional)",
            }
        )
        # Validar que las credenciales no estén vacías
        self._validate_credentials()
        logger.info("Credenciales de CDmon configuradas correctamente")

    def _validate_credentials(self):
        """Validate that the credentials are not empty."""
        api_key = self.credentials.conf("api_key")
        
        logger.debug("Validando credenciales de CDmon")
        if not api_key:
            logger.error("Clave API de CDmon no proporcionada")
            raise errors.PluginError("CDmon API key is required.")
        
        # El dominio ahora es opcional, no validamos su presencia
        logger.debug("Credenciales de CDmon validadas correctamente")

    def _get_http_session(self):
        """Get or create an HTTP session with retry capabilities.

        Returns:
            requests.Session: A session with retry configuration.
        """
        if self._session is None:
            logger.debug("Creando nueva sesión HTTP con capacidad de reintentos")
            self._session = requests.Session()
            retry_strategy = Retry(
                total=MAX_RETRIES,
                backoff_factor=RETRY_BACKOFF_FACTOR,
                status_forcelist=RETRY_STATUS_FORCELIST,
                allowed_methods=["POST"]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self._session.mount("https://", adapter)
            logger.debug(
                "Configuración de reintentos: total=%d, backoff_factor=%f, status_forcelist=%s",
                MAX_RETRIES, RETRY_BACKOFF_FACTOR, RETRY_STATUS_FORCELIST
            )
        return self._session

    def _perform(self, domain, validation_name, validation):
        """Perform a dns-01 challenge by creating a TXT record.

        Args:
            domain: The domain being validated.
            validation_name: The name of the DNS record to create.
            validation: The validation content.

        Raises:
            errors.PluginError: If there is an error creating the TXT record.
        """
        logger.info(
            "Realizando desafío dns-01 para %s con valor de validación %s",
            validation_name, validation
        )
        try:
            # Detectar el dominio base si no está en las credenciales
            self._detect_base_domain(domain, validation_name)
            
            subdomain = self._get_cdmon_subdomain(validation_name)
            logger.debug("Subdominio extraído: '%s'", subdomain)
            self._create_txt_record(subdomain, validation, validation_name)
            logger.info(
                "Registro TXT creado exitosamente para %s", validation_name
            )
        except Exception as e:
            logger.error(
                "Error al crear registro TXT para %s: %s",
                validation_name, str(e), exc_info=True
            )
            raise errors.PluginError(f"Error creating TXT record: {e}")

    def _cleanup(self, domain, validation_name, validation):
        """Clean up the TXT record which would have been created by _perform.

        Args:
            domain: The domain being validated.
            validation_name: The name of the DNS record to delete.
            validation: The validation content.
        """
        logger.info(
            "Limpiando registro TXT para %s", validation_name
        )
        try:
            # Usar el dominio base detectado previamente
            subdomain = self._get_cdmon_subdomain(validation_name)
            logger.debug("Subdominio extraído para limpieza: '%s'", subdomain)
            self._delete_txt_record(subdomain, validation, validation_name)
            logger.info(
                "Registro TXT eliminado exitosamente para %s", validation_name
            )
        except Exception as e:
            logger.error(
                "Error al eliminar registro TXT para %s: %s",
                validation_name, str(e), exc_info=True
            )
            # Unificar manejo de errores: lanzar excepción en lugar de solo registrar
            raise errors.PluginError(f"Error cleaning up TXT record: {e}")

    def _detect_base_domain(self, domain, validation_name):
        """Detect the base domain for a validation name.
        
        This method tries to determine the base domain that should be used
        with the CDmon API, either from the credentials file or by analyzing
        the validation name.
        
        Args:
            domain: The domain being validated.
            validation_name: The name of the DNS record to create/delete.
            
        Returns:
            str: The detected base domain.
            
        Raises:
            errors.PluginError: If the base domain cannot be determined.
        """
        # Si ya tenemos el dominio base para este nombre de validación, lo usamos
        if validation_name in self._domain_map:
            return self._domain_map[validation_name]
            
        # Intentar obtener el dominio de las credenciales
        config_domain = self.credentials.conf("domain")
        if config_domain and validation_name.endswith(config_domain):
            logger.debug(
                "Usando dominio de configuración: %s para %s",
                config_domain, validation_name
            )
            self._domain_map[validation_name] = config_domain
            return config_domain
            
        # Si no está en las credenciales, intentar detectarlo del nombre de validación
        # Primero, eliminar el prefijo _acme-challenge si está presente
        clean_name = validation_name
        if clean_name.startswith(f"{ACME_CHALLENGE_PREFIX}."):
            clean_name = clean_name[len(f"{ACME_CHALLENGE_PREFIX}."):]
            
        # Intentar encontrar el dominio base analizando el nombre de validación
        parts = clean_name.split('.')
        
        # Probar diferentes combinaciones de partes como dominio base
        # Empezamos con el dominio completo y vamos quitando subdominios
        for i in range(len(parts) - 1):
            potential_domain = '.'.join(parts[i:])
            
            # Si el dominio que estamos validando es parte del potencial dominio base
            if domain.endswith(potential_domain):
                logger.info(
                    "Dominio base detectado automáticamente: %s para %s",
                    potential_domain, validation_name
                )
                self._domain_map[validation_name] = potential_domain
                return potential_domain
                
        # Si llegamos aquí, no pudimos detectar el dominio base
        if config_domain:
            # Usar el dominio de configuración como último recurso
            logger.warning(
                "No se pudo detectar automáticamente el dominio base para %s, "
                "usando dominio de configuración: %s",
                validation_name, config_domain
            )
            self._domain_map[validation_name] = config_domain
            return config_domain
        else:
            # No tenemos dominio base, intentar usar el dominio que se está validando
            logger.warning(
                "No se pudo detectar automáticamente el dominio base para %s, "
                "intentando usar el dominio que se está validando: %s",
                validation_name, domain
            )
            self._domain_map[validation_name] = domain
            return domain

    def _get_cdmon_subdomain(self, validation_name):
        """Extract the subdomain from the validation name.

        Args:
            validation_name: The full domain name for validation.

        Returns:
            str: The extracted subdomain without the ACME challenge prefix.
        """
        # Obtener el dominio base para este nombre de validación
        domain = self._get_base_domain_for_validation(validation_name)
        
        logger.debug(
            "Extrayendo subdominio de %s (dominio base: %s)",
            validation_name, domain
        )
        
        if not validation_name.endswith(domain):
            logger.warning(
                "El nombre de validación %s no termina con el dominio %s",
                validation_name, domain
            )
            return ""
            
        # Extraer el subdominio quitando el dominio base y el punto
        subdomain = validation_name[:-len(domain)-1]
        logger.debug("Subdominio extraído (con prefijo): '%s'", subdomain)
        
        # Quitar el prefijo _acme-challenge si está presente
        if subdomain.startswith(f"{ACME_CHALLENGE_PREFIX}."):
            subdomain = subdomain[len(f"{ACME_CHALLENGE_PREFIX}."):]
        elif subdomain == ACME_CHALLENGE_PREFIX:
            subdomain = ""
            
        logger.debug("Subdominio final (sin prefijo): '%s'", subdomain)
        return subdomain

    def _get_base_domain_for_validation(self, validation_name):
        """Get the base domain for a validation name.
        
        This method returns the base domain that should be used with the CDmon API
        for a specific validation name.
        
        Args:
            validation_name: The name of the DNS record to create/delete.
            
        Returns:
            str: The base domain to use.
            
        Raises:
            errors.PluginError: If the base domain cannot be determined.
        """
        # Si ya tenemos el dominio base para este nombre de validación, lo usamos
        if validation_name in self._domain_map:
            return self._domain_map[validation_name]
            
        # Si no lo tenemos, intentar obtenerlo de las credenciales
        config_domain = self.credentials.conf("domain")
        if config_domain:
            self._domain_map[validation_name] = config_domain
            return config_domain
            
        # Si no tenemos el dominio base, no podemos continuar
        logger.error(
            "No se pudo determinar el dominio base para %s. "
            "Debe especificar el dominio en el archivo de credenciales o "
            "ejecutar _perform primero para detectarlo automáticamente.",
            validation_name
        )
        raise errors.PluginError(
            f"Could not determine base domain for {validation_name}. "
            "Please specify the domain in the credentials file or "
            "run _perform first to auto-detect it."
        )

    def _format_acme_subdomain(self, subdomain):
        """Format the subdomain with the ACME challenge prefix.

        Args:
            subdomain: The subdomain without the ACME challenge prefix.

        Returns:
            str: The formatted subdomain with the ACME challenge prefix.
        """
        if not subdomain:
            formatted = ACME_CHALLENGE_PREFIX
        else:
            formatted = f"{ACME_CHALLENGE_PREFIX}.{subdomain}"
            
        logger.debug(
            "Subdominio formateado con prefijo ACME: '%s'", formatted
        )
        return formatted

    def _find_txt_records(self, domain, subdomain, api_key):
        """Find TXT records for a specific subdomain.

        Args:
            domain: The base domain.
            subdomain: The subdomain to search for.
            api_key: The CDmon API key.

        Returns:
            list: A list of matching TXT records.
        """
        acme_subdomain = self._format_acme_subdomain(subdomain)
        logger.debug(
            "Buscando registros TXT para %s.%s", acme_subdomain, domain
        )
        
        records = self._list_dns_records(domain, api_key)
        
        # Validar la respuesta de la API
        if not isinstance(records, dict) or 'data' not in records:
            logger.warning(
                "Formato de respuesta inesperado de la API de CDmon: %s", 
                records
            )
            return []
            
        result = records.get('data', {}).get('result', [])
        if not isinstance(result, list):
            logger.warning(
                "Formato de resultado inesperado de la API de CDmon: %s", 
                result
            )
            return []
            
        txt_records = [
            record for record in result
            if record.get('type') == 'TXT' and record.get('host') == acme_subdomain
        ]
        
        logger.debug(
            "Encontrados %d registros TXT para %s.%s", 
            len(txt_records), acme_subdomain, domain
        )
        return txt_records

    def _create_txt_record(self, subdomain, validation, validation_name):
        """Create a TXT record using the CDmon API.

        Args:
            subdomain: The subdomain without the ACME challenge prefix.
            validation: The validation content.
            validation_name: The full validation name (used for domain detection).
        """
        api_key = self.credentials.conf("api_key")
        domain = self._get_base_domain_for_validation(validation_name)
        
        acme_subdomain = self._format_acme_subdomain(subdomain)
        txt_value = f'"{validation}"'
        
        logger.debug(
            "Preparando para crear/actualizar registro TXT para %s.%s con valor %s",
            acme_subdomain, domain, txt_value
        )
        
        # Verificar si el registro ya existe
        txt_records = self._find_txt_records(domain, subdomain, api_key)
        
        if txt_records:
            logger.info(
                "Actualizando registro TXT existente para %s.%s",
                acme_subdomain, domain
            )
            self._edit_dns_txt_record(domain, acme_subdomain, txt_value, api_key)
            logger.debug("Registro TXT actualizado correctamente")
        else:
            logger.info(
                "Creando nuevo registro TXT para %s.%s",
                acme_subdomain, domain
            )
            self._create_dns_txt_record(domain, acme_subdomain, txt_value, api_key)
            logger.debug("Registro TXT creado correctamente")

    def _delete_txt_record(self, subdomain, validation, validation_name):
        """Delete a TXT record using the CDmon API.

        Args:
            subdomain: The subdomain without the ACME challenge prefix.
            validation: The validation content.
            validation_name: The full validation name (used for domain detection).
        """
        api_key = self.credentials.conf("api_key")
        domain = self._get_base_domain_for_validation(validation_name)
        
        acme_subdomain = self._format_acme_subdomain(subdomain)
        
        logger.debug(
            "Preparando para eliminar registro TXT para %s.%s",
            acme_subdomain, domain
        )
        
        # Verificar si el registro existe
        txt_records = self._find_txt_records(domain, subdomain, api_key)
        
        if txt_records:
            logger.info(
                "Eliminando registro TXT para %s.%s",
                acme_subdomain, domain
            )
            self._delete_dns_txt_record(domain, acme_subdomain, api_key)
            logger.debug("Registro TXT eliminado correctamente")
        else:
            logger.info(
                "No se encontró registro TXT para %s.%s, nada que eliminar",
                acme_subdomain, domain
            )

    def _make_api_request(self, endpoint, data, api_key):
        """Make a request to the CDmon API with retry capability.

        Args:
            endpoint: The API endpoint to call.
            data: The data to send in the request.
            api_key: The CDmon API key.

        Returns:
            dict: The JSON response from the API.

        Raises:
            errors.PluginError: If there is an error making the API request.
        """
        headers = {
            'Accept': 'application/json',
            'apikey': api_key
        }
        
        url = f'{API_BASE_URL}/{endpoint}'
        logger.debug(
            "Realizando solicitud a la API de CDmon: %s", url
        )
        logger.debug("Datos de la solicitud: %s", json.dumps(data))
        
        session = self._get_http_session()
        
        try:
            start_time = time.time()
            response = session.post(
                url,
                headers=headers,
                json=data,
                timeout=30  # Añadir timeout para evitar bloqueos indefinidos
            )
            elapsed_time = time.time() - start_time
            
            logger.debug(
                "Respuesta de la API recibida en %.2f segundos, código: %d",
                elapsed_time, response.status_code
            )
            
            response.raise_for_status()  # Lanzar excepción para códigos de error HTTP
            
            # Validar que la respuesta sea JSON válido
            try:
                result = response.json()
                logger.debug(
                    "Respuesta JSON válida recibida: %s", 
                    json.dumps(result)[:200] + ('...' if len(json.dumps(result)) > 200 else '')
                )
                return result
            except ValueError:
                logger.error(
                    "Respuesta JSON inválida de la API de CDmon: %s",
                    response.text[:200] + ('...' if len(response.text) > 200 else '')
                )
                raise errors.PluginError(
                    f"Invalid JSON response from CDmon API: {response.text}"
                )
                
        except requests.exceptions.Timeout:
            logger.error(
                "Timeout al comunicarse con la API de CDmon (endpoint: %s)",
                endpoint
            )
            raise errors.PluginError(f"Timeout communicating with CDmon API")
        except requests.exceptions.ConnectionError:
            logger.error(
                "Error de conexión al comunicarse con la API de CDmon (endpoint: %s)",
                endpoint
            )
            raise errors.PluginError(f"Connection error communicating with CDmon API")
        except requests.exceptions.HTTPError as e:
            logger.error(
                "Error HTTP %d al comunicarse con la API de CDmon (endpoint: %s): %s",
                e.response.status_code, endpoint, e.response.text
            )
            raise errors.PluginError(f"HTTP error from CDmon API: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(
                "Error al comunicarse con la API de CDmon (endpoint: %s): %s",
                endpoint, str(e), exc_info=True
            )
            raise errors.PluginError(f"Error communicating with CDmon API: {e}")

    def _list_dns_records(self, domain, api_key):
        """List DNS records for a domain.

        Args:
            domain: The domain to list records for.
            api_key: The CDmon API key.

        Returns:
            dict: The JSON response from the API.
        """
        logger.debug("Listando registros DNS para el dominio %s", domain)
        data = {
            'data': {
                'domain': domain
            }
        }
        return self._make_api_request('getDnsRecords', data, api_key)

    def _create_dns_txt_record(self, domain, subdomain, value, api_key):
        """Create a TXT record.

        Args:
            domain: The domain to create the record for.
            subdomain: The subdomain to create the record for.
            value: The value of the TXT record.
            api_key: The CDmon API key.

        Returns:
            dict: The JSON response from the API.
        """
        logger.debug(
            "Creando registro TXT para %s.%s con valor %s",
            subdomain, domain, value
        )
        data = {
            'data': {
                'domain': domain,
                'type': 'TXT',
                'ttl': DEFAULT_TTL,
                'host': subdomain,
                'value': value
            }
        }
        return self._make_api_request('dnsrecords/create', data, api_key)

    def _edit_dns_txt_record(self, domain, subdomain, value, api_key):
        """Edit an existing TXT record.

        Args:
            domain: The domain to edit the record for.
            subdomain: The subdomain to edit the record for.
            value: The new value of the TXT record.
            api_key: The CDmon API key.

        Returns:
            dict: The JSON response from the API.
        """
        logger.debug(
            "Editando registro TXT para %s.%s con nuevo valor %s",
            subdomain, domain, value
        )
        current_record = {
            'host': subdomain,
            'type': 'TXT'
        }
        new_record = {
            'ttl': DEFAULT_TTL,
            'value': value
        }
        data = {
            'data': {
                'domain': domain,
                'current': current_record,
                'new': new_record
            }
        }
        return self._make_api_request('dnsrecords/edit', data, api_key)

    def _delete_dns_txt_record(self, domain, subdomain, api_key):
        """Delete a TXT record.

        Args:
            domain: The domain to delete the record from.
            subdomain: The subdomain to delete the record from.
            api_key: The CDmon API key.

        Returns:
            dict: The JSON response from the API.
        """
        logger.debug(
            "Eliminando registro TXT para %s.%s",
            subdomain, domain
        )
        data = {
            'data': {
                'domain': domain,
                'host': subdomain,
                'type': 'TXT'
            }
        }
        return self._make_api_request('dnsrecords/delete', data, api_key)
