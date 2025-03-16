"""Tests for certbot_dns_cdmon.dns_cdmon."""

import unittest
import mock

from certbot.plugins.dns_test_common import BaseAuthenticatorTest
from certbot.tests.util import test_util

from certbot_dns_cdmon.dns_cdmon import Authenticator


class AuthenticatorTest(BaseAuthenticatorTest):
    def setUp(self):
        from certbot.plugins.dns_test_common import DOMAIN
        super(AuthenticatorTest, self).setUp()

        self.config = mock.MagicMock(
            cdmon_credentials=self.credential_path,
            cdmon_propagation_seconds=0  # don't wait during tests
        )

        self.auth = Authenticator(self.config, "cdmon")

        self.mock_client = mock.MagicMock()
        # _get_cdmon_client | pylint: disable=protected-access
        self.auth._get_cdmon_client = mock.MagicMock(return_value=self.mock_client)

    def test_perform(self):
        self.auth._perform('example.com', 'test.example.com', 'validation')
        self.mock_client.add_txt_record.assert_called_with('test.example.com', 'validation')

    def test_cleanup(self):
        self.auth._cleanup('example.com', 'test.example.com', 'validation')
        self.mock_client.del_txt_record.assert_called_with('test.example.com', 'validation')


if __name__ == "__main__":
    unittest.main()  # pragma: no cover