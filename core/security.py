import os
import base64
import subprocess
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class SecurityManager:
    def __init__(self):
        self.salt = b'careercaster_v1_salt' # In a real app, this would be stored securely or unique per user
        self.key = self._derive_key()
        self.fernet = Fernet(self.key)

    def _get_hardware_id(self):
        """
        Retrieves a unique hardware ID for the machine.
        On Windows, we use the UUID from wmic.
        """
        try:
            cmd = 'wmic csproduct get uuid'
            uuid_str = subprocess.check_output(cmd, shell=True).decode().split('\n')[1].strip()
            return uuid_str.encode()
        except Exception:
            # Fallback to a generic ID if wmic fails
            import uuid
            return str(uuid.getnode()).encode()

    def _derive_key(self):
        """
        Derives a 32-byte key from the hardware ID and salt.
        """
        password = self._get_hardware_id()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password))

    def encrypt_data(self, data_str):
        """
        Encrypts a string and returns the encrypted bytes.
        """
        return self.fernet.encrypt(data_str.encode())

    def decrypt_data(self, encrypted_bytes):
        """
        Decrypts bytes and returns the original string.
        """
        return self.fernet.decrypt(encrypted_bytes).decode()
