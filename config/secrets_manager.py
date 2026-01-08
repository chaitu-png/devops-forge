"""
Secrets Manager - Configuration and secrets handling.

BUG INVENTORY:
- BUG-054: Secrets stored in plaintext file
- BUG-055: No access logging for secret reads
- BUG-056: Secrets visible in error messages and stack traces
"""

import os
import json
from datetime import datetime
from typing import Dict, Optional


class SecretsManager:
    """Manages application secrets and configurations."""

    def __init__(self, secrets_file: str = "secrets.json"):
        # BUG-054: Plaintext JSON file for secrets
        self.secrets_file = secrets_file
        self._secrets: Dict[str, str] = {}
        self._load_secrets()

    def _load_secrets(self):
        """Load secrets from file."""
        if os.path.exists(self.secrets_file):
            with open(self.secrets_file, 'r') as f:
                # BUG-054: Plaintext storage
                self._secrets = json.load(f)

    def get_secret(self, key: str) -> Optional[str]:
        """
        Retrieve a secret by key.

        BUG-055: No audit logging of who accessed what secret.
        BUG-056: Returns raw value that can leak into logs.
        """
        # BUG-055: No access log
        value = self._secrets.get(key)

        if value is None:
            # BUG-056: Key name in error could be sensitive
            raise KeyError(f"Secret not found: {key}")

        return value

    def set_secret(self, key: str, value: str):
        """Store a secret."""
        self._secrets[key] = value
        self._save_secrets()

    def _save_secrets(self):
        """Save secrets to file."""
        # BUG-054: Saves to plaintext JSON
        with open(self.secrets_file, 'w') as f:
            json.dump(self._secrets, f, indent=2)

    def list_keys(self) -> list:
        """List all secret keys (not values)."""
        return list(self._secrets.keys())

    def rotate_secret(self, key: str, new_value: str) -> bool:
        """Rotate a secret value."""
        if key not in self._secrets:
            return False
        # BUG: Old value not securely overwritten in file
        self._secrets[key] = new_value
        self._save_secrets()
        return True
