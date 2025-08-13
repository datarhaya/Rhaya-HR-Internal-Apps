import streamlit as st
import os
import toml
from google.oauth2 import service_account

class SecretsManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SecretsManager, cls).__new__(cls)
            cls._instance._secrets = None
            cls._instance._load_secrets()
        return cls._instance
    
    def _load_secrets(self):
        """Load secrets based on environment"""
        if os.getenv("RENDER"):
            # Render environment - load from secret file
            secrets_path = "/etc/secrets/secrets"
            if os.path.exists(secrets_path):
                with open(secrets_path, 'r') as f:
                    self._secrets = toml.load(f)
            else:
                raise ValueError("Render secrets file not found at /etc/secrets/secrets")
        else:
            # Local/Streamlit Cloud - use st.secrets
            self._secrets = st.secrets
    
    def get(self, key, default=None):
        """Get a secret value"""
        return self._secrets.get(key, default)
    
    def get_nested(self, *keys):
        """Get nested secret value like secrets["firebase_auth"]["project_id"]"""
        value = self._secrets
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value
    
    def get_section(self, section):
        """Get an entire section"""
        return dict(self._secrets.get(section, {}))
    
    def get_firebase_credentials(self):
        """Get Firebase credentials"""
        firebase_auth = self.get_section("firebase_auth")
        if firebase_auth:
            return service_account.Credentials.from_service_account_info(firebase_auth)
        else:
            raise ValueError("firebase_auth section not found")

# Global instance
secrets = SecretsManager()