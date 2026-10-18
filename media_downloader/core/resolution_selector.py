"""Resolution selector helper for configuring download quality and format selection."""

from __future__ import annotations

from typing import Optional


class ResolutionSelector:
    """Handles resolution selection logic for video downloads."""

    # Display name to height mapping
    RESOLUTIONS: dict[str, Optional[int]] = {
        "1080p": 1080,
        "2160p": 2160,
        "1440p": 1440,
        "720p": 720,
        "480p": 480,
        "360p": 360,
        "best": None,  # None means best available
    }

    @classmethod
    def get_target_height(cls, resolution_key: str) -> int | None:
        """Get target height in pixels from resolution key.

        Args:
            resolution_key: Resolution identifier (e.g., '1080p', '720p', 'best').

        Returns:
            Target height integer in pixels, or None for best available.
        """
        return cls.RESOLUTIONS.get(resolution_key)

    @classmethod
    def get_ytdlp_format_string(cls, resolution_key: str, mode: str = "video") -> str:
        """Get yt-dlp format string for given resolution and mode.

        Args:
            resolution_key: Key like '1080p', '720p', 'best'.
            mode: 'video' or 'audio'. Defaults to 'video'.

        Returns:
            Formatted yt-dlp format selector string.
        """
        if mode == "audio":
            return "bestaudio/best"

        height = cls.RESOLUTIONS.get(resolution_key)
        if height is None:
            return "bestvideo+bestaudio/best"

        return f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/bestvideo+bestaudio/best"

    @classmethod
    def get_ytdlp_sort_string(cls, resolution_key: str) -> str:
        """Get yt-dlp format sort string.

        Args:
            resolution_key: Key like '1080p', '720p', 'best'.

        Returns:
            Sort format string (e.g. 'res:1080,ext:mp4:m4a').
        """
        height = cls.RESOLUTIONS.get(resolution_key)
        if height is None:
            return "res,ext:mp4:m4a"
        return f"res:{height},ext:mp4:m4a"

    @classmethod
    def get_closest_resolution(cls, available_heights: list[int], target: int) -> int:
        """Find the closest available resolution to the target.

        Prefers resolutions <= target. If none available, picks the closest above.

        Args:
            available_heights: List of integer heights available for the media.
            target: Desired target height in pixels.

        Returns:
            The selected height in pixels.
        """
        if not available_heights:
            return target

        # Prefer heights <= target, pick highest among those
        lower = [h for h in available_heights if h <= target]
        if lower:
            return max(lower)

        # Otherwise pick closest above
        return min(available_heights, key=lambda h: abs(h - target))
