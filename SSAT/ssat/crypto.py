import os
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from a password and salt using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return kdf.derive(password.encode())

def encrypt_payload(payload: str, password: str) -> str:
    """
    Encrypt a payload string using AES-256-GCM.
    Returns a base64 encoded string containing salt + nonce + ciphertext.
    """
    salt = os.urandom(16)
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, payload.encode(), None)
    
    # Bundle salt, nonce, and ciphertext
    combined = salt + nonce + ciphertext
    return base64.b64encode(combined).decode('utf-8')

def decrypt_payload(encrypted_payload_b64: str, password: str) -> str:
    """
    Decrypt a base64 encoded payload using AES-256-GCM.
    """
    try:
        combined = base64.b64decode(encrypted_payload_b64)
        salt = combined[:16]
        nonce = combined[16:28]
        ciphertext = combined[28:]
        
        key = derive_key(password, salt)
        aesgcm = AESGCM(key)
        
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted.decode('utf-8')
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")
