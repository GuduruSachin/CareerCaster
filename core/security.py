import os
import base64
import subprocess
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class SecurityManager:
    def __init__(self):
        print("Security: Initializing SecurityManager...", flush=True)
        self.salt = b'careercaster_v1_salt' # In a real app, this would be stored securely or unique per user
        print("Security: Deriving key...", flush=True)
        self.key = self._derive_key()
        print("Security: Key derived.", flush=True)
        self.fernet = Fernet(self.key)
        print("Security: Fernet initialized.", flush=True)

    def _get_hardware_id(self):
        """
        Retrieves a unique hardware ID for the machine.
        On Windows, we use the UUID from wmic.
        """
        print("Security: Retrieving hardware ID...", flush=True)
        try:
            cmd = 'wmic csproduct get uuid'
            print(f"Security: Running command: {cmd}", flush=True)
            # Use a timeout to prevent indefinite hang
            output = subprocess.check_output(cmd, shell=True, timeout=10).decode()
            uuid_str = output.split('\n')[1].strip()
            print(f"Security: Hardware ID retrieved: {uuid_str[:5]}...", flush=True)
            return uuid_str.encode()
        except Exception as e:
            print(f"Security: Hardware ID retrieval failed: {e}. Using fallback.", flush=True)
            # Fallback to a generic ID if wmic fails
            import uuid
            node_id = str(uuid.getnode()).encode()
            print(f"Security: Fallback ID: {node_id[:5]}...", flush=True)
            return node_id

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
