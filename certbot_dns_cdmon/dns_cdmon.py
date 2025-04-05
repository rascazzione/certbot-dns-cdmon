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
                "domain": "Base domain managed by CDmon (optional)",
            }
        )

    def _perform(self, domain, validation_name, validation):
        try:
            logger.info(f"Performing validation for {validation_name}")
            subdomain_info = self._get_cdmon_subdomain(validation_name)
            logger.info(f"Extracted subdomain info: {subdomain_info}")
            self._create_txt_record(subdomain_info, validation)
            time.sleep(self.conf('propagation-seconds') or 10)  # Add propagation delay here
        except Exception as e:
            raise errors.PluginError(f"Error creating TXT record: {e}")

    def _cleanup(self, domain, validation_name, validation):
        """
        Clean up the TXT record which would have been created by _perform.
        """
        try:
            logger.info(f"Cleaning up validation for {validation_name}")
            subdomain_info = self._get_cdmon_subdomain(validation_name)
            logger.info(f"Extracted subdomain info for cleanup: {subdomain_info}")
            self._delete_txt_record(subdomain_info, validation)
        except Exception as e:
            logger.warning(f"Error cleaning up TXT record: {e}")

    def _get_cdmon_subdomain(self, validation_name):
        """
        Extract the subdomain and domain from the validation name.
        Returns a tuple of (subdomain, domain).
        """
        logger.info(f"Processing validation name: {validation_name}")
        
        # Remove _acme-challenge prefix if present
        if validation_name.startswith("_acme-challenge."):
            domain_name = validation_name[len("_acme-challenge."):]
            logger.info(f"Removed _acme-challenge prefix, domain_name: {domain_name}")
        else:
            domain_name = validation_name
            logger.info(f"No _acme-challenge prefix found, domain_name: {domain_name}")
            
        # Try to use domain from credentials if available and matches
        config_domain = self.credentials.conf("domain")
        if config_domain and domain_name.endswith(config_domain):
            logger.info(f"Using configured domain: {config_domain}")
            # Extract subdomain using the configured domain
            if domain_name == config_domain:
                # It's the apex domain
                logger.info(f"Apex domain detected, returning: ('', {config_domain})")
                return ("", config_domain)
            else:
                # It's a subdomain
                subdomain = domain_name[:-len(config_domain)-1]  # Remove domain and dot
                logger.info(f"Subdomain detected, returning: ('{subdomain}', {config_domain})")
                return (subdomain, config_domain)
        
        # If we don't have a matching configured domain, extract domain from validation_name
        parts = domain_name.split('.')
        logger.info(f"Domain parts: {parts}")
        
        if len(parts) <= 1:
            # Single part domain, use as is
            logger.info(f"Single part domain, returning: ('', {domain_name})")
            return ("", domain_name)
            
        # For multi-part domains, assume the last two parts form the domain
        if len(parts) == 2:
            # It's likely the apex domain (example.com)
            logger.info(f"Two-part domain, returning: ('', {domain_name})")
            return ("", domain_name)
        else:
            # It's likely a subdomain (sub.example.com)
            domain = '.'.join(parts)  # Use the full domain
            subdomain = ""  # No subdomain
            if len(parts) > 2:
                # Extract subdomain and domain
                domain = '.'.join(parts[-2:])  # Last two parts for domain
                subdomain = '.'.join(parts[:-2])  # Everything else for subdomain
            
            logger.info(f"Multi-part domain, returning: ('{subdomain}', {domain})")
            return (subdomain, domain)


    def _create_txt_record(self, subdomain_info, validation):
        """
        Create a TXT record using the CDmon API.
        """
        api_key = self.credentials.conf("api_key")
        subdomain, domain = subdomain_info
        
        if not domain:
            # If no domain was extracted, try to use the one from credentials
            domain = self.credentials.conf("domain")
            if not domain:
                raise errors.PluginError("No domain specified in credentials or validation name")
        
        logger.info(f"Using domain: {domain} for TXT record")
        
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

    def _delete_txt_record(self, subdomain_info, validation):
        """
        Delete a TXT record using the CDmon API.
        """
        api_key = self.credentials.conf("api_key")
        subdomain, domain = subdomain_info
        
        if not domain:
            # If no domain was extracted, try to use the one from credentials
            domain = self.credentials.conf("domain")
            if not domain:
                logger.warning("No domain specified in credentials or validation name, skipping cleanup")
                return
        
        logger.info(f"Using domain: {domain} for deleting TXT record")
        
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
        headers = {'Accept': 'application/json', 'apikey': api_key}
        response = requests.post(f'https://api-domains.cdmon.services/api-domains/{endpoint}', headers=headers, json=data)
        if response.status_code == 200:
            return response.json()
        else:
            # Extract error message from JSON response if available
            try:
                error_data = response.json()
                error_msg = error_data.get('message', response.text)
            except json.JSONDecodeError:
                error_msg = response.text
            raise errors.PluginError(f"CDmon API error: {response.status_code} - {error_msg}")

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
