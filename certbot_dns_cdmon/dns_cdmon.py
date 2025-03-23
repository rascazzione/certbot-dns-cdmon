"""CDmon DNS Authenticator."""
import json
import logging
import os
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

# Nombres de variables de entorno específicos para evitar conflictos
ENV_API_KEY = "API_KEY_CDMON"
ENV_DOMAIN = "DOMAIN_CDMON"


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
        self._api_key = None   # Almacena la clave API para uso posterior
        self._domain = None    # Almacena el dominio base opcional
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
        
        # Inicializar atributos para almacenar credenciales
        self._api_key = None
        self._domain = None
        
        # Intentar leer credenciales del archivo INI
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
        """Validate that the credentials are not empty and check for environment variables."""
        # Intentar obtener la clave API del archivo de credenciales
        api_key = self.credentials.conf("api_key")
        
        # Si no está en el archivo, buscar en variables de entorno específicas para CDmon
        if not api_key and ENV_API_KEY in os.environ:
            api_key = os.environ[ENV_API_KEY]
            logger.debug("Clave API obtenida de variable de entorno %s", ENV_API_KEY)
        
        logger.debug("Validando credenciales de CDmon")
        if not api_key:
            logger.error("Clave API de CDmon no proporcionada")
            raise errors.PluginError("CDmon API key is required.")
        
        # Guardar la clave API para uso posterior
        self._api_key = api_key
        
        # Intentar obtener el dominio del archivo de credenciales
        domain = self.credentials.conf("domain")
        
        # Si no está en el archivo, buscar en variables de entorno específicas para CDmon
        if not domain and ENV_DOMAIN in os.environ:
            domain = os.environ[ENV_DOMAIN]
            logger.debug("Dominio obtenido de variable de entorno %s", ENV_DOMAIN)
        
        # El dominio sigue siendo opcional
        if domain:
            self._domain = domain
        
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
            
        # Intentar obtener el dominio de las credenciales (ahora almacenado en self._domain)
        config_domain = self._domain
        if config_domain and validation_name.endswith(config_domain):
            logger.debug(
                "Usando dominio de configuración: %s para %s",
                config_domain, validation_name
            )
            self._domain_map[validation_name] = config_domain
            return config_domain
            
        # Si no está en las credenciales, intentar detectarlo del nombre de validación
        # Primero, eliminar el prefijo _acme-challenge si está presente
        name_parts = validation_name.split(".")
        if name_parts[0] == ACME_CHALLENGE_PREFIX:
            name_parts = name_parts[1:]
            
        # Intentar diferentes combinaciones de partes del nombre para encontrar el dominio base
        for i in range(len(name_parts) - 1):
            possible_domain = ".".join(name_parts[i:])
            if possible_domain == domain or domain.endswith("." + possible_domain):
                logger.debug(
                    "Dominio base detectado automáticamente: %s para %s",
                    possible_domain, validation_name
                )
                self._domain_map[validation_name] = possible_domain
                return possible_domain
                
        # Si llegamos aquí, no pudimos detectar el dominio base
        logger.error(
            "No se pudo determinar el dominio base para %s", validation_name
        )
        raise errors.PluginError(
            f"Could not determine base domain for {validation_name}. "
            f"Please specify the domain in the credentials file or environment variable {ENV_DOMAIN}."
        )

    def _get_base_domain_for_validation(self, validation_name):
        """Get the base domain for a validation name.
        
        This method returns the base domain for a validation name, either from
        the domain map or by detecting it.
        
        Args:
            validation_name: The name of the DNS record to create/delete.
            
        Returns:
            str: The base domain.
            
        Raises:
            errors.PluginError: If the base domain cannot be determined.
        """
        # Si ya tenemos el dominio base para este nombre de validación, lo usamos
        if validation_name in self._domain_map:
            return self._domain_map[validation_name]
            
        # Si no está en el mapa, intentar detectarlo
        logger.error(
            "No se encontró el dominio base para %s en el mapa de dominios", 
            validation_name
        )
        raise errors.PluginError(
            f"Could not find base domain for {validation_name}. "
            f"Please ensure _perform is called before _cleanup."
        )

    def _get_cdmon_subdomain(self, validation_name):
        """Get the CDmon subdomain from a validation name.
        
        This method extracts the subdomain part from a validation name,
        removing the base domain and handling the _acme-challenge prefix.
        
        Args:
            validation_name: The name of the DNS record to create/delete.
            
        Returns:
            str: The subdomain part, or empty string for the root domain.
        """
        # Obtener el dominio base para este nombre de validación
        base_domain = self._get_base_domain_for_validation(validation_name)
        
        # Eliminar el dominio base del nombre de validación
        if validation_name.endswith("." + base_domain):
            subdomain = validation_name[:-len(base_domain) - 1]
        elif validation_name == base_domain:
            subdomain = ""
        else:
            logger.warning(
                "El nombre de validación %s no coincide con el dominio base %s",
                validation_name, base_domain
            )
            return ""
            
        logger.debug(
            "Subdominio extraído: '%s' de '%s' con dominio base '%s'",
            subdomain, validation_name, base_domain
        )
        return subdomain

    def _format_acme_subdomain(self, subdomain):
        """Format a subdomain for ACME challenge.
        
        This method adds the _acme-challenge prefix to a subdomain if needed.
        
        Args:
            subdomain: The subdomain part.
            
        Returns:
            str: The formatted subdomain with _acme-challenge prefix.
        """
        # Si el subdominio ya incluye el prefijo _acme-challenge, devolverlo tal cual
        if subdomain.startswith(ACME_CHALLENGE_PREFIX):
            return subdomain
            
        # Si el subdominio está vacío, devolver solo el prefijo
        if not subdomain:
            return ACME_CHALLENGE_PREFIX
            
        # En caso contrario, añadir el prefijo al subdominio
        return f"{ACME_CHALLENGE_PREFIX}.{subdomain}"

    def _find_txt_records(self, domain, subdomain):
        """Find TXT records for a domain and subdomain.
        
        This method queries the CDmon API to find TXT records for a domain
        and subdomain.
        
        Args:
            domain: The domain to query.
            subdomain: The subdomain to filter by.
            
        Returns:
            list: A list of TXT records.
        """
        logger.debug(
            "Buscando registros TXT para dominio '%s' y subdominio '%s'",
            domain, subdomain
        )
        
        # Formatear el subdominio para el desafío ACME
        acme_subdomain = self._format_acme_subdomain(subdomain)
        
        # Construir la URL y los datos para la solicitud
        url = f"{API_BASE_URL}/dns/records"
        data = {
            "domain": domain,
            "token": self._api_key
        }
        
        # Realizar la solicitud a la API
        try:
            session = self._get_http_session()
            response = session.post(url, json=data)
            response.raise_for_status()
            
            # Procesar la respuesta
            response_data = response.json()
            if not response_data.get("success", False):
                logger.error(
                    "Error en la respuesta de la API: %s",
                    response_data.get("message", "Unknown error")
                )
                return []
                
            # Filtrar los registros TXT que coinciden con el subdominio ACME
            records = response_data.get("data", {}).get("records", [])
            txt_records = [
                record for record in records
                if record.get("type") == "TXT" and record.get("name") == acme_subdomain
            ]
            
            logger.debug(
                "Encontrados %d registros TXT para %s.%s",
                len(txt_records), acme_subdomain, domain
            )
            return txt_records
            
        except requests.exceptions.RequestException as e:
            logger.error(
                "Error al consultar registros DNS: %s", str(e), exc_info=True
            )
            return []

    def _create_txt_record(self, subdomain, validation, validation_name):
        """Create a TXT record for validation.
        
        This method creates a TXT record with the validation content.
        
        Args:
            subdomain: The subdomain part.
            validation: The validation content.
            validation_name: The full validation name (for logging).
            
        Raises:
            errors.PluginError: If there is an error creating the record.
        """
        logger.debug(
            "Creando registro TXT para subdominio '%s' con valor '%s'",
            subdomain, validation
        )
        
        # Obtener el dominio base para este nombre de validación
        domain = self._get_base_domain_for_validation(validation_name)
        
        # Formatear el subdominio para el desafío ACME
        acme_subdomain = self._format_acme_subdomain(subdomain)
        
        # Verificar si ya existe un registro TXT para este subdominio
        txt_records = self._find_txt_records(domain, subdomain)
        
        if txt_records:
            # Si ya existe un registro, actualizarlo
            record_id = txt_records[0].get("id")
            logger.debug(
                "Actualizando registro TXT existente con ID %s", record_id
            )
            self._edit_dns_txt_record(domain, acme_subdomain, validation, record_id)
        else:
            # Si no existe, crear uno nuevo
            logger.debug("Creando nuevo registro TXT")
            self._create_dns_txt_record(domain, acme_subdomain, validation)

    def _delete_txt_record(self, subdomain, validation, validation_name):
        """Delete a TXT record used for validation.
        
        This method deletes a TXT record with the validation content.
        
        Args:
            subdomain: The subdomain part.
            validation: The validation content.
            validation_name: The full validation name (for logging).
            
        Raises:
            errors.PluginError: If there is an error deleting the record.
        """
        logger.debug(
            "Eliminando registro TXT para subdominio '%s'",
            subdomain
        )
        
        # Obtener el dominio base para este nombre de validación
        domain = self._get_base_domain_for_validation(validation_name)
        
        # Verificar si existe un registro TXT para este subdominio
        txt_records = self._find_txt_records(domain, subdomain)
        
        if txt_records:
            # Si existe un registro, eliminarlo
            record_id = txt_records[0].get("id")
            logger.debug(
                "Eliminando registro TXT con ID %s", record_id
            )
            self._delete_dns_record(domain, record_id)
        else:
            # Si no existe, no hacer nada
            logger.debug(
                "No se encontró registro TXT para eliminar"
            )

    def _create_dns_txt_record(self, domain, name, content):
        """Create a DNS TXT record via the CDmon API.
        
        Args:
            domain: The domain to create the record for.
            name: The name of the record.
            content: The content of the record.
            
        Raises:
            errors.PluginError: If there is an error creating the record.
        """
        logger.debug(
            "Creando registro DNS TXT para dominio '%s', nombre '%s', contenido '%s'",
            domain, name, content
        )
        
        # Construir la URL y los datos para la solicitud
        url = f"{API_BASE_URL}/dns/record/add"
        data = {
            "domain": domain,
            "token": self._api_key,
            "type": "TXT",
            "name": name,
            "content": content,
            "ttl": DEFAULT_TTL
        }
        
        # Realizar la solicitud a la API
        try:
            session = self._get_http_session()
            response = session.post(url, json=data)
            response.raise_for_status()
            
            # Procesar la respuesta
            response_data = response.json()
            if not response_data.get("success", False):
                error_msg = response_data.get("message", "Unknown error")
                logger.error(
                    "Error al crear registro DNS: %s", error_msg
                )
                raise errors.PluginError(f"Error creating DNS record: {error_msg}")
                
            logger.info(
                "Registro DNS TXT creado exitosamente"
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(
                "Error al crear registro DNS: %s", str(e), exc_info=True
            )
            raise errors.PluginError(f"Error creating DNS record: {e}")

    def _edit_dns_txt_record(self, domain, name, content, record_id):
        """Edit a DNS TXT record via the CDmon API.
        
        Args:
            domain: The domain to edit the record for.
            name: The name of the record.
            content: The new content of the record.
            record_id: The ID of the record to edit.
            
        Raises:
            errors.PluginError: If there is an error editing the record.
        """
        logger.debug(
            "Editando registro DNS TXT con ID %s para dominio '%s', nombre '%s', contenido '%s'",
            record_id, domain, name, content
        )
        
        # Construir la URL y los datos para la solicitud
        url = f"{API_BASE_URL}/dns/record/edit"
        data = {
            "domain": domain,
            "token": self._api_key,
            "type": "TXT",
            "name": name,
            "content": content,
            "ttl": DEFAULT_TTL,
            "id": record_id
        }
        
        # Realizar la solicitud a la API
        try:
            session = self._get_http_session()
            response = session.post(url, json=data)
            response.raise_for_status()
            
            # Procesar la respuesta
            response_data = response.json()
            if not response_data.get("success", False):
                error_msg = response_data.get("message", "Unknown error")
                logger.error(
                    "Error al editar registro DNS: %s", error_msg
                )
                raise errors.PluginError(f"Error editing DNS record: {error_msg}")
                
            logger.info(
                "Registro DNS TXT editado exitosamente"
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(
                "Error al editar registro DNS: %s", str(e), exc_info=True
            )
            raise errors.PluginError(f"Error editing DNS record: {e}")

    def _delete_dns_record(self, domain, record_id):
        """Delete a DNS record via the CDmon API.
        
        Args:
            domain: The domain to delete the record from.
            record_id: The ID of the record to delete.
            
        Raises:
            errors.PluginError: If there is an error deleting the record.
        """
        logger.debug(
            "Eliminando registro DNS con ID %s para dominio '%s'",
            record_id, domain
        )
        
        # Construir la URL y los datos para la solicitud
        url = f"{API_BASE_URL}/dns/record/delete"
        data = {
            "domain": domain,
            "token": self._api_key,
            "id": record_id
        }
        
        # Realizar la solicitud a la API
        try:
            session = self._get_http_session()
            response = session.post(url, json=data)
            response.raise_for_status()
            
            # Procesar la respuesta
            response_data = response.json()
            if not response_data.get("success", False):
                error_msg = response_data.get("message", "Unknown error")
                logger.error(
                    "Error al eliminar registro DNS: %s", error_msg
                )
                raise errors.PluginError(f"Error deleting DNS record: {error_msg}")
                
            logger.info(
                "Registro DNS eliminado exitosamente"
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(
                "Error al eliminar registro DNS: %s", str(e), exc_info=True
            )
            raise errors.PluginError(f"Error deleting DNS record: {e}")
