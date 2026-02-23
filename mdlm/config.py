"""Secure credential storage for mdlm.

API key precedence (highest → lowest):
  1. MDLM_API_KEY environment variable
  2. ~/.config/mdlm/config  (mode 0600)
"""

import configparser
import os
import stat
import sys
from pathlib import Path

_CONFIG_DIR = Path.home() / ".config" / "mdlm"
_CONFIG_FILE = _CONFIG_DIR / "config"
_SECTION = "credentials"
_KEY_FIELD = "api_key"


def _enforce_permissions(path: Path) -> None:
    """Ensure the config file is readable only by the owner."""
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600


def save_api_key(api_key: str) -> None:
    """Persist an API key to the secure config file."""
    if not api_key.startswith("mdlm_"):
        print("Error: API key must start with 'mdlm_'.", file=sys.stderr)
        sys.exit(1)

    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Write the file with restrictive permissions from the start
    config = configparser.ConfigParser()
    config[_SECTION] = {_KEY_FIELD: api_key}

    # Use os.open so we can set mode=0o600 atomically on creation
    fd = os.open(_CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        config.write(f)

    # Enforce even if the file already existed with wrong perms
    _enforce_permissions(_CONFIG_FILE)


def get_api_key() -> str:
    """Return the API key, or exit with a clear error if not found."""
    # 1. Environment variable takes precedence
    env_key = os.environ.get("MDLM_API_KEY", "").strip()
    if env_key:
        return env_key

    # 2. Config file
    if _CONFIG_FILE.exists():
        # Warn if permissions are too open (another user could read it)
        file_stat = _CONFIG_FILE.stat()
        if file_stat.st_mode & (stat.S_IRGRP | stat.S_IROTH):
            print(
                f"Warning: {_CONFIG_FILE} is readable by others. "
                "Run `chmod 600` on it to fix this.",
                file=sys.stderr,
            )

        config = configparser.ConfigParser()
        config.read(_CONFIG_FILE)
        key = config.get(_SECTION, _KEY_FIELD, fallback="").strip()
        if key:
            return key

    print(
        "Error: No API key found.\n"
        "Run `mdlm configure` to set your API key,\n"
        "or set the MDLM_API_KEY environment variable.",
        file=sys.stderr,
    )
    sys.exit(1)


def get_api_url() -> str:
    """Return the base API URL (overridable for testing)."""
    url = os.environ.get("MDLM_API_URL", "https://markdownlm.com").rstrip("/")
    if not url.startswith("https://"):
        print(
            f"Error: MDLM_API_URL must use HTTPS. Got: {url!r}",
            file=sys.stderr,
        )
        sys.exit(1)
    return url
