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
    
    def __getitem__(self, key):
        """Allow dict-like access: secrets["key"]"""
        return self._secrets[key]
    
    def __contains__(self, key):
        """Allow 'in' operator: "key" in secrets"""
        return key in self._secrets
    
    def get(self, key, default=None):
        """Get a secret value with optional default"""
        return self._secrets.get(key, default)
    
    def get_nested(self, *keys):
        """Get nested secret value like secrets.get_nested("firebase_auth", "project_id")"""
        value = self._secrets
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value
    
    def get_section(self, section):
        """Get an entire section as a dictionary"""
        section_data = self._secrets.get(section, {})
        return dict(section_data) if section_data else {}
    
    def get_firebase_credentials(self):
        """Get Firebase credentials object"""
        firebase_auth = self.get_section("firebase_auth")
        if firebase_auth:
            return service_account.Credentials.from_service_account_info(firebase_auth)
        else:
            raise ValueError("firebase_auth section not found in secrets")
    
    # Convenience properties for common secrets
    @property
    def github_pat(self):
        """Get GitHub Personal Access Token"""
        return self.get("GITHUB_PAT")
    
    @property
    def firebase_auth(self):
        """Get Firebase auth section"""
        return self.get_section("firebase_auth")
    
    @property
    def email_config(self):
        """Get email configuration section"""
        return self.get_section("email")
    
    @property
    def firebase_storage(self):
        """Get Firebase storage configuration"""
        return self.get_section("firebase_storage")

# Global instance
secrets = SecretsManager()

# Convenience functions for common use cases
def get_firebase_credentials():
    """Get Firebase credentials - can be imported directly"""
    return secrets.get_firebase_credentials()

def get_email_config():
    """Get email configuration - can be imported directly"""
    return secrets.email_config

def get_firebase_storage_config():
    """Get Firebase storage config - can be imported directly"""
    return secrets.firebase_storage