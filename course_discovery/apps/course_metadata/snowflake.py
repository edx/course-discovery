import snowflake.connector
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, load_pem_private_key
from django.conf import settings


def build_private_key_bytes(private_key_pem, passphrase=None):
    """
    Convert PEM private key into DER bytes required by Snowflake.
    """
    passphrase_bytes = passphrase.encode('utf-8') if passphrase else None

    p_key = load_pem_private_key(
        private_key_pem.encode('utf-8'),
        password=passphrase_bytes,
        backend=default_backend(),
    )

    return p_key.private_bytes(
        encoding=Encoding.DER,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )


def get_snowflake_connection():
    """
    Create Snowflake connection using key pair authentication.
    """
    connection_kwargs = {
        'user': settings.SNOWFLAKE_SERVICE_USER,
        'private_key': build_private_key_bytes(
            settings.SNOWFLAKE_SERVICE_PRIVKEY,
            getattr(settings, 'SNOWFLAKE_SERVICE_PASSPHRASE', None),
        ),
        'account': settings.SNOWFLAKE_ACCOUNT,
        'database': settings.SNOWFLAKE_DATABASE,
    }

    role = getattr(settings, 'SNOWFLAKE_ROLE', None)
    if role:
        connection_kwargs['role'] = role

    return snowflake.connector.connect(**connection_kwargs)
