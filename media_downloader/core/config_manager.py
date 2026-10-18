"""Configuration manager for the media downloader application."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class ConfigManager:
    """Manages application configuration stored in JSON file."""

    DEFAULT_CONFIG: dict[str, Any] = {
        "language": "tr",
        "theme": "system",  # "system", "dark", "light"
        "window_geometry": None,  # "WxH+X+Y" format
        "download_dir": "",  # empty means user must select
        "resolution": "1080p",
        "format": "video",  # "video" or "audio"
        "last_used_platform": None,
    }

    def __init__(self, config_path: str | Path | None = None) -> None:
        """Initialize configuration manager with optional custom path.

        Args:
            config_path: Path to configuration JSON file. If None, defaults to config.json in root.
        """
        if config_path is None:
            self.config_path = Path(os.path.dirname(os.path.abspath(__file__))).parent / "config.json"
        else:
            self.config_path = Path(config_path)

        self._config: dict[str, Any] = dict(self.DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        """Load config from JSON file. Creates default if not exists."""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                    if isinstance(loaded_data, dict):
                        # Preserve defaults for any keys missing in the file
                        config = dict(self.DEFAULT_CONFIG)
                        config.update(loaded_data)
                        self._config = config
                    else:
                        # Malformed content, revert to defaults and persist
                        self._config = dict(self.DEFAULT_CONFIG)
                        self.save()
            else:
                self.save()
        except (json.JSONDecodeError, OSError):
            self._config = dict(self.DEFAULT_CONFIG)
            self.save()

    def save(self) -> None:
        """Save current config to JSON file."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
        except OSError as exc:
            # Handle file write errors gracefully
            print(f"Warning: Failed to save config to {self.config_path}: {exc}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value.

        Args:
            key: Setting key name.
            default: Default value if key is not present.

        Returns:
            The configuration value.
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a config value and auto-save.

        Args:
            key: Setting key name.
            value: Value to store.
        """
        self._config[key] = value
        self.save()
