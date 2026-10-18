"""Dependency manager for handling dynamic package installations and FFmpeg discovery."""

from __future__ import annotations

import importlib
import importlib.util
import os
import shutil
import subprocess
import sys
from typing import Any, Callable, Optional


class DependencyManager:
    """Manages dynamic installation of platform-specific packages and ffmpeg."""

    # Platform to required packages mapping
    PLATFORM_DEPS: dict[str, dict[str, list[str]]] = {
        "youtube": {
            "primary": ["yt_dlp"],
            "fallback": ["pytubefix"],
        },
        "instagram": {
            "primary": ["yt_dlp"],
            "fallback": ["instaloader", "gallery_dl"],
        },
        "twitter": {
            "primary": ["yt_dlp"],
            "fallback": ["gallery_dl"],
        },
        "tiktok": {
            "primary": ["yt_dlp"],
            "fallback": ["gallery_dl"],
        },
    }

    # Import name to pip package name mapping
    PACKAGE_NAMES: dict[str, str] = {
        "yt_dlp": "yt-dlp",
        "pytubefix": "pytubefix",
        "instaloader": "instaloader",
        "gallery_dl": "gallery-dl",
        "imageio_ffmpeg": "imageio-ffmpeg",
        "static_ffmpeg": "static-ffmpeg",
    }

    def __init__(self) -> None:
        """Initialize dependency manager."""
        self._ffmpeg_path: Optional[str] = None

    @staticmethod
    def is_installed(module_name: str) -> bool:
        """Check if a Python module is installed.

        Args:
            module_name: Python module import name.

        Returns:
            True if the module can be found, False otherwise.
        """
        try:
            return importlib.util.find_spec(module_name) is not None
        except (ModuleNotFoundError, ValueError, AttributeError):
            return False

    def install_package(
        self, pip_name: str, log_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """Install a package via pip. Returns True on success.

        Args:
            pip_name: Pip package name or mapped module name.
            log_callback: Optional callback for progress messages.

        Returns:
            True if installed successfully, False otherwise.
        """
        resolved_name = self.PACKAGE_NAMES.get(pip_name, pip_name)
        if log_callback:
            log_callback(f"Installing {resolved_name}...")

        try:
            cmd = [sys.executable, "-m", "pip", "install", resolved_name]
            kwargs: dict[str, Any] = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
                "check": False,
            }
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            process = subprocess.run(cmd, **kwargs)
            if process.returncode == 0:
                importlib.invalidate_caches()
                if log_callback:
                    log_callback(f"Successfully installed {resolved_name}.")
                return True
            else:
                err_msg = (process.stderr or process.stdout or "").strip()
                if log_callback:
                    log_callback(f"Failed to install {resolved_name}: {err_msg}")
                return False
        except Exception as exc:
            if log_callback:
                log_callback(f"Error installing {resolved_name}: {exc}")
            return False

    def ensure_platform_deps(
        self, platform: str, log_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """Check and install all dependencies for a platform (primary + fallback).

        Args:
            platform: Platform name ('youtube', 'instagram', 'twitter', 'tiktok').
            log_callback: Optional callback for progress messages.

        Returns:
            True if all dependencies for the platform are installed, False otherwise.
        """
        platform_key = platform.lower() if platform else ""
        platform_info = self.PLATFORM_DEPS.get(platform_key)
        if not platform_info:
            if log_callback:
                log_callback(f"No dependencies configured for platform: {platform}")
            return True

        # Combine primary and fallback dependencies while preserving unique order
        all_modules: list[str] = []
        for category in ("primary", "fallback"):
            for mod in platform_info.get(category, []):
                if mod not in all_modules:
                    all_modules.append(mod)

        all_installed = True
        for mod in all_modules:
            if not self.is_installed(mod):
                pip_pkg = self.PACKAGE_NAMES.get(mod, mod)
                if log_callback:
                    log_callback(f"Dependency '{mod}' not found. Installing '{pip_pkg}'...")
                success = self.install_package(pip_pkg, log_callback)
                if not success:
                    all_installed = False
            else:
                if log_callback:
                    log_callback(f"Dependency '{mod}' is already installed.")

        return all_installed

    def get_ffmpeg_path(
        self, log_callback: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """Get ffmpeg binary path. Checks system PATH first, then tries imageio-ffmpeg/static-ffmpeg.

        Args:
            log_callback: Optional callback for progress messages.

        Returns:
            Path to the ffmpeg executable, or None if not found and cannot be installed.
        """
        if self._ffmpeg_path and os.path.isfile(self._ffmpeg_path):
            return self._ffmpeg_path

        if log_callback:
            log_callback("Checking for FFmpeg...")

        # 1. Check if ffmpeg in PATH via shutil.which
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg and os.path.isfile(system_ffmpeg):
            self._ffmpeg_path = system_ffmpeg
            if log_callback:
                log_callback(f"FFmpeg found in PATH: {system_ffmpeg}")
            return system_ffmpeg

        # 2. Try imageio_ffmpeg.get_ffmpeg_exe()
        if self.is_installed("imageio_ffmpeg"):
            try:
                import imageio_ffmpeg

                exe_path = imageio_ffmpeg.get_ffmpeg_exe()
                if exe_path and os.path.isfile(exe_path):
                    self._ffmpeg_path = exe_path
                    if log_callback:
                        log_callback(f"FFmpeg found via imageio-ffmpeg: {exe_path}")
                    return exe_path
            except Exception as exc:
                if log_callback:
                    log_callback(f"Failed to access imageio-ffmpeg: {exc}")

        # 3. Try static_ffmpeg
        if self.is_installed("static_ffmpeg"):
            try:
                import static_ffmpeg

                if hasattr(static_ffmpeg, "add_paths"):
                    static_ffmpeg.add_paths()
                resolved = shutil.which("ffmpeg")
                if resolved and os.path.isfile(resolved):
                    self._ffmpeg_path = resolved
                    if log_callback:
                        log_callback(f"FFmpeg found via static-ffmpeg: {resolved}")
                    return resolved
            except Exception as exc:
                if log_callback:
                    log_callback(f"Failed to access static-ffmpeg: {exc}")

        # 4. Install imageio-ffmpeg and retry
        if log_callback:
            log_callback("FFmpeg not found. Attempting to install imageio-ffmpeg...")

        installed = self.install_package("imageio-ffmpeg", log_callback)
        if installed:
            try:
                importlib.invalidate_caches()
                imageio_ffmpeg = importlib.import_module("imageio_ffmpeg")
                exe_path = imageio_ffmpeg.get_ffmpeg_exe()
                if exe_path and os.path.isfile(exe_path):
                    self._ffmpeg_path = exe_path
                    if log_callback:
                        log_callback(f"FFmpeg ready via imageio-ffmpeg: {exe_path}")
                    return exe_path
            except Exception as exc:
                if log_callback:
                    log_callback(f"Error accessing imageio-ffmpeg after installation: {exc}")

        if log_callback:
            log_callback("FFmpeg could not be found or installed.")
        return None
