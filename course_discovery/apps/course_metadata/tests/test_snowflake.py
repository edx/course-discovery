from unittest import mock

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, Encoding, NoEncryption, PrivateFormat
from django.test import TestCase

from course_discovery.apps.course_metadata.snowflake import build_private_key_bytes, get_snowflake_connection


class TestSnowflakeHelpers(TestCase):
    """Tests for Snowflake helper functions."""

    def _generate_pem_key(self, passphrase=None):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )

        encryption = (
            BestAvailableEncryption(passphrase.encode("utf-8"))
            if passphrase
            else NoEncryption()
        )

        return private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=encryption,
        ).decode("utf-8")

    def test_build_private_key_bytes_without_passphrase(self):
        pem = self._generate_pem_key()

        result = build_private_key_bytes(pem)

        self.assertIsInstance(result, bytes)
        self.assertEqual(result[0], 0x30)

    def test_build_private_key_bytes_with_passphrase(self):
        passphrase = "test-passphrase"

        pem = self._generate_pem_key(passphrase=passphrase)

        result = build_private_key_bytes(pem, passphrase)

        self.assertIsInstance(result, bytes)
        self.assertEqual(result[0], 0x30)

    @mock.patch(
        "course_discovery.apps.course_metadata.snowflake.build_private_key_bytes"
    )
    @mock.patch(
        "course_discovery.apps.course_metadata.snowflake.snowflake.connector.connect"
    )
    @mock.patch(
        "course_discovery.apps.course_metadata.snowflake.settings"
    )
    def test_get_snowflake_connection(
        self,
        mock_settings,
        mock_connect,
        mock_build_private_key,
    ):
        mock_settings.SNOWFLAKE_SERVICE_USER = "ENTERPRISE_SERVICE_USER"
        mock_settings.SNOWFLAKE_SERVICE_PRIVKEY = "private-key"
        mock_settings.SNOWFLAKE_SERVICE_PASSPHRASE = "passphrase"
        mock_settings.SNOWFLAKE_ACCOUNT = "edx.us-east-1"
        mock_settings.SNOWFLAKE_DATABASE = "prod"
        mock_settings.SNOWFLAKE_ROLE = "ENTERPRISE_SERVICE_USER_ROLE"

        mock_build_private_key.return_value = b"fake-private-key"

        get_snowflake_connection()

        mock_build_private_key.assert_called_once_with(
            "private-key",
            "passphrase",
        )

        mock_connect.assert_called_once_with(
            user="ENTERPRISE_SERVICE_USER",
            private_key=b"fake-private-key",
            account="edx.us-east-1",
            database="prod",
            role="ENTERPRISE_SERVICE_USER_ROLE",
        )

    @mock.patch(
        "course_discovery.apps.course_metadata.snowflake.build_private_key_bytes"
    )
    @mock.patch(
        "course_discovery.apps.course_metadata.snowflake.snowflake.connector.connect"
    )
    @mock.patch(
        "course_discovery.apps.course_metadata.snowflake.settings"
    )
    def test_get_snowflake_connection_without_role(
        self,
        mock_settings,
        mock_connect,
        mock_build_private_key,
    ):
        mock_settings.SNOWFLAKE_SERVICE_USER = "ENTERPRISE_SERVICE_USER"
        mock_settings.SNOWFLAKE_SERVICE_PRIVKEY = "private-key"
        mock_settings.SNOWFLAKE_SERVICE_PASSPHRASE = "passphrase"
        mock_settings.SNOWFLAKE_ACCOUNT = "edx.us-east-1"
        mock_settings.SNOWFLAKE_DATABASE = "prod"
        mock_settings.SNOWFLAKE_ROLE = None

        mock_build_private_key.return_value = b"fake-private-key"

        get_snowflake_connection()

        mock_build_private_key.assert_called_once_with(
            "private-key",
            "passphrase",
        )

        mock_connect.assert_called_once_with(
            user="ENTERPRISE_SERVICE_USER",
            private_key=b"fake-private-key",
            account="edx.us-east-1",
            database="prod",
        )
