import os
import json
import logging

logger = logging.getLogger("trinetra-agents.vault")

def load_vault_secrets(vault_dir="/vault/secrets"):
    """
    Loads secrets from the mounted Vault directory into environment variables.
    """
    if os.path.exists(vault_dir) and os.path.isdir(vault_dir):
        try:
            for entry in os.listdir(vault_dir):
                entry_path = os.path.join(vault_dir, entry)
                if os.path.isfile(entry_path):
                    if entry == "api-keys":
                        try:
                            with open(entry_path, "r") as f:
                                content = f.read().strip()
                            try:
                                data = json.loads(content)
                                if isinstance(data, dict):
                                    for k, v in data.items():
                                        os.environ[k] = str(v).strip()
                            except json.JSONDecodeError as e:
                                logger.debug(f"Failed to parse vault api-keys JSON: {e}. Trying key=value format.")
                                for line in content.splitlines():
                                    if "=" in line:
                                        k, v = line.split("=", 1)
                                        os.environ[k.strip()] = v.strip()
                        except Exception as e:
                            logger.warning(f"Failed to load vault api-keys file: {e}")
                    else:
                        try:
                            with open(entry_path, "r") as f:
                                os.environ[entry] = f.read().strip()
                        except Exception as e:
                            logger.warning(f"Failed to load vault secret file {entry}: {e}")
        except Exception as e:
            logger.warning(f"Failed to read vault directory {vault_dir}: {e}")
