#!/usr/bin/env python3
"""Generate an RSA private key for AI config transport encryption."""

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pem_text = pem_bytes.decode("utf-8")
    env_value = pem_text.replace("\n", "\\n")

    print("# AI_CONFIG_PRIVATE_KEY_PEM")
    print(pem_text)
    print("# export command")
    print(f"export AI_CONFIG_PRIVATE_KEY_PEM='{env_value}'")


if __name__ == "__main__":
    main()
