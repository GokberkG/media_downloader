"""URL detection module for identifying media platforms and content types."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse, parse_qs


class URLDetector:
    """Detects platform and content type from a given URL."""

    # Platform regex patterns
    PATTERNS: dict[str, dict[str, Any]] = {
        "youtube": {
            "domains": [r"(?:www\.)?youtube\.com", r"youtu\.be", r"m\.youtube\.com"],
            "shorts": r"/shorts/[\w-]+",
            "video": r"(?:/watch\?|/embed/|youtu\.be/)",
        },
        "instagram": {
            "domains": [r"(?:www\.)?instagram\.com", r"(?:www\.)?instagr\.am"],
            "reels": r"/reels?/",
            "post": r"/p/",
        },
        "twitter": {
            "domains": [r"(?:www\.)?(?:twitter|x)\.com", r"(?:www\.)?(?:vxtwitter|fxtwitter)\.com"],
            "tweet": r"/status/\d+",
        },
        "tiktok": {
            "domains": [r"(?:www\.)?tiktok\.com", r"vm\.tiktok\.com", r"vt\.tiktok\.com"],
            "tiktok": r"(?:/video/\d+|/@[\w.]+/video/|/t/)",
        },
    }

    @classmethod
    def detect(cls, url: str) -> dict[str, str | None]:
        """Detect platform and content type from URL.

        Args:
            url: The raw URL string to inspect.

        Returns:
            dict with keys:
                - platform: 'youtube'|'instagram'|'twitter'|'tiktok'|None
                - content_type: 'video'|'shorts'|'post'|'reels'|'tweet'|'tiktok'|None
                - url: cleaned URL string
        """
        if not url or not isinstance(url, str):
            return {
                "platform": None,
                "content_type": None,
                "url": url if isinstance(url, str) else "",
            }

        # Clean URL: strip whitespace and ensure https://
        cleaned_url = url.strip()
        if not cleaned_url:
            return {"platform": None, "content_type": None, "url": ""}

        if cleaned_url.startswith("http://"):
            cleaned_url = "https://" + cleaned_url[7:]
        elif cleaned_url.startswith("//"):
            cleaned_url = "https:" + cleaned_url
        elif not re.match(r"^https?://", cleaned_url, re.IGNORECASE):
            cleaned_url = "https://" + cleaned_url

        try:
            parsed = urlparse(cleaned_url)
            hostname = (parsed.hostname or "").lower()
        except Exception:
            return {"platform": None, "content_type": None, "url": cleaned_url}

        # Detect platform by matching hostname against platform domains
        detected_platform: str | None = None
        for platform_name, config in cls.PATTERNS.items():
            for domain_pattern in config["domains"]:
                if re.search(domain_pattern, hostname, re.IGNORECASE):
                    detected_platform = platform_name
                    break
            if detected_platform:
                break

        if not detected_platform:
            return {
                "platform": None,
                "content_type": None,
                "url": cleaned_url,
            }

        # Determine content type based on URL path and patterns
        content_type: str | None = None

        if detected_platform == "youtube":
            if re.search(cls.PATTERNS["youtube"]["shorts"], cleaned_url, re.IGNORECASE):
                content_type = "shorts"
            elif re.search(cls.PATTERNS["youtube"]["video"], cleaned_url, re.IGNORECASE):
                content_type = "video"
            else:
                content_type = "video"

        elif detected_platform == "instagram":
            if re.search(cls.PATTERNS["instagram"]["reels"], cleaned_url, re.IGNORECASE):
                content_type = "reels"
            elif re.search(cls.PATTERNS["instagram"]["post"], cleaned_url, re.IGNORECASE):
                content_type = "post"
            else:
                content_type = "post"

        elif detected_platform == "twitter":
            if re.search(cls.PATTERNS["twitter"]["tweet"], cleaned_url, re.IGNORECASE):
                content_type = "tweet"
            else:
                content_type = "tweet"

        elif detected_platform == "tiktok":
            if re.search(cls.PATTERNS["tiktok"]["tiktok"], cleaned_url, re.IGNORECASE):
                content_type = "tiktok"
            else:
                content_type = "tiktok"

        return {
            "platform": detected_platform,
            "content_type": content_type,
            "url": cleaned_url,
        }
