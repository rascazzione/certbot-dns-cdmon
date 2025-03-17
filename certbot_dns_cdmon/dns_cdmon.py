"""CDmon DNS Authenticator."""
import json
import logging
import time
import requests

from certbot import errors
from certbot.plugins import dns_common
from certbot.plugins.dns_common import CredentialsConfiguration

logger = logging.getLogger(__name__)


class Authenticator(dns_common.DNSAuthenticator):
    """DNS Authenticator for CDmon

    This Authenticator uses the CDmon API to fulfill a dns-01 challenge.
    """

    description = "Obtain certificates using a DNS TXT record (via CDmon API)"

    def __init__(self, *args, **kwargs):
        super(Authenticator, self).__init__(*args, **kwargs)
        self.credentials = None

    @classmethod
    def add_parser_arguments(cls, add):
        super(Authenticator, cls).add_parser_arguments(add, default_propagation_seconds=90)
        add("credentials", help="CDmon API credentials INI file.")

    def more_info(self):
        return "This plugin configures a DNS TXT record to respond to a dns-01 challenge using the CDmon API."

    def _setup_credentials(self):
        self.credentials = self._configure_credentials(
            "credentials",
            "CDmon API credentials INI file",
            {
                "api_key": "API key for CDmon API",
                "domain": "Base domain managed by CDmon",
            }
        )

    def _perform(self, domain, validation_name, validation):
        """
        Perform a dns-01 challenge by creating a TXT record.
        """
        try:
            subdomain = self._get_cdmon_subdomain(validation_name)
            self._create_txt_record(subdomain, validation)
        except Exception as e:
            raise errors.PluginError(f"Error creating TXT record: {e}")

    def _cleanup(self, domain, validation_name, validation):
        """
        Clean up the TXT record which would have been created by _perform.
        """
        try:
            subdomain = self._get_cdmon_subdomain(validation_name)
            self._delete_txt_record(subdomain, validation)
        except Exception as e:
            logger.warning(f"Error cleaning up TXT record: {e}")

    def _get_cdmon_subdomain(self, validation_name):
        domain = self.credentials.conf("domain")
        if validation_name.endswith(domain):
            subdomain = validation_name[:-len(domain)-1]  # Remueve el dominio y el punto
            # Si empieza con '_acme-challenge.' se elimina ese prefijo
            if subdomain.startswith("_acme-challenge."):
                subdomain = subdomain[len("_acme-challenge."):]
            elif subdomain == "_acme-challenge":
                subdomain = ""
            return subdomain
        return ""


    def _create_txt_record(self, subdomain, validation):
        """
        Create a TXT record using the CDmon API.
        """
        api_key = self.credentials.conf("api_key")
        domain = self.credentials.conf("domain")
        
        if subdomain == "_acme-challenge":
            acme_subdomain = "_acme-challenge"
        else:
            acme_subdomain = f"_acme-challenge.{subdomain}" if subdomain else "_acme-challenge"
        
        txt_value = f'"{validation}"'
        
        # Check if record already exists
        records = self._list_dns_records(domain, api_key)
        txt_records = [record for record in records.get('data', {}).get('result', []) 
                      if record.get('type') == 'TXT' and record.get('host') == acme_subdomain]
        
        if txt_records:
            logger.info(f"Updating existing TXT record for {acme_subdomain}.{domain}")
            self._edit_dns_txt_record(domain, acme_subdomain, txt_value, api_key)
        else:
            logger.info(f"Creating new TXT record for {acme_subdomain}.{domain}")
            self._create_dns_txt_record(domain, acme_subdomain, txt_value, api_key)

    def _delete_txt_record(self, subdomain, validation):
        """
        Delete a TXT record using the CDmon API.
        """
        api_key = self.credentials.conf("api_key")
        domain = self.credentials.conf("domain")
        
        # Format the subdomain for CDmon API
        acme_subdomain = f"_acme-challenge.{subdomain}" if subdomain else "_acme-challenge"
        
        # Check if record exists
        records = self._list_dns_records(domain, api_key)
        txt_records = [record for record in records.get('data', {}).get('result', []) 
                      if record.get('type') == 'TXT' and record.get('host') == acme_subdomain]
        
        if txt_records:
            logger.info(f"Deleting TXT record for {acme_subdomain}.{domain}")
            self._delete_dns_txt_record(domain, acme_subdomain, api_key)

    def _make_api_request(self, endpoint, data, api_key):
        """
        Make a request to the CDmon API.
        """
        headers = {
            'Accept': 'application/json',
            'apikey': api_key
        }
        response = requests.post(
            f'https://api-domains.cdmon.services/api-domains/{endpoint}', 
            headers=headers, 
            json=data
        )
        if response.status_code == 200:
            return response.json()
        else:
            raise errors.PluginError(f"CDmon API error: {response.status_code} - {response.text}")

    def _list_dns_records(self, domain, api_key):
        """
        List DNS records for a domain.
        """
        data = {
            'data': {
                'domain': domain
            }
        }
        return self._make_api_request('getDnsRecords', data, api_key)

    def _create_dns_txt_record(self, domain, subdomain, value, api_key):
        """
        Create a TXT record.
        """
        data = {
            'data': {
                'domain': domain,
                'type': 'TXT',
                'ttl': 60,
                'host': subdomain,
                'value': value
            }
        }
        return self._make_api_request('dnsrecords/create', data, api_key)

    def _edit_dns_txt_record(self, domain, subdomain, value, api_key):
        """
        Edit an existing TXT record.
        """
        current_record = {
            'host': subdomain,
            'type': 'TXT'
        }
        new_record = {
            'ttl': 60,
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
        """
        Delete a TXT record.
        """
        data = {
            'data': {
                'domain': domain,
                'host': subdomain,
                'type': 'TXT'
            }
        }
        return self._make_api_request('dnsrecords/delete', data, api_key)