"""Cryptographic utilities for AgentAuth."""

import base64
import hashlib
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def derive_key_from_password(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte encryption key from a password using PBKDF2.
    
    Args:
        password: The master password
        salt: The salt bytes (should be unique per vault)
        
    Returns:
        A 32-byte key suitable for Fernet encryption
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))
    return key


def generate_salt() -> bytes:
    """Generate a random 16-byte salt for key derivation.
    
    Returns:
        Random salt bytes
    """
    import secrets
    return secrets.token_bytes(16)


def get_fernet_cipher(password: str, salt: bytes) -> Fernet:
    """Create a Fernet cipher instance from a password and salt.
    
    Args:
        password: The master password
        salt: The salt bytes
        
    Returns:
        A Fernet cipher instance
    """
    key = derive_key_from_password(password, salt)
    return Fernet(key)


def encrypt_data(data: bytes, password: str, salt: bytes) -> bytes:
    """Encrypt data using Fernet encryption.
    
    Args:
        data: The data to encrypt
        password: The master password
        salt: The salt bytes
        
    Returns:
        Encrypted data as bytes
    """
    cipher = get_fernet_cipher(password, salt)
    return cipher.encrypt(data)


def decrypt_data(encrypted_data: bytes, password: str, salt: bytes) -> bytes:
    """Decrypt data using Fernet decryption.
    
    Args:
        encrypted_data: The encrypted data
        password: The master password
        salt: The salt bytes
        
    Returns:
        Decrypted data as bytes
        
    Raises:
        cryptography.fernet.InvalidToken: If decryption fails (wrong password)
    """
    cipher = get_fernet_cipher(password, salt)
    return cipher.decrypt(encrypted_data)


def hash_password(password: str) -> str:
    """Hash a password using SHA256 (for storage in config).
    
    Note: This is only used for quick verification, not security.
    The actual encryption uses the raw password with PBKDF2.
    
    Args:
        password: The password to hash
        
    Returns:
        Hex-encoded SHA256 hash
    """
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

