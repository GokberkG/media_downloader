"""Main download orchestrator engine managing downloads and two-stage fallback."""

import os
import threading
from typing import Callable, Optional

from core.url_detector import URLDetector
from core.dependency_manager import DependencyManager
from core.platforms import youtube, instagram, twitter, tiktok


class DownloaderEngine:
    """Main download orchestrator with 2-stage fallback."""

    PLATFORM_MODULES = {
        "youtube": youtube,
        "instagram": instagram,
        "twitter": twitter,
        "tiktok": tiktok,
    }

    def __init__(self):
        self.dep_manager = DependencyManager()
        self._current_thread: Optional[threading.Thread] = None
        self._cancel_flag = threading.Event()

    def download(self, url: str, output_dir: str, resolution_key: str,
                 mode: str, progress_callback: Callable = None,
                 log_callback: Callable = None,
                 status_callback: Callable = None,
                 completion_callback: Callable = None):
        """Start download in a worker thread.

        Args:
            url: Media URL to download
            output_dir: Destination folder
            resolution_key: Requested resolution ('1080p', '720p', etc.)
            mode: 'video' or 'audio'
            progress_callback: Called with progress dict
            log_callback: Called with log messages
            status_callback: Called with status string ('downloading', 'complete', 'failed')
            completion_callback: Called with (success: bool, filepath: str or error msg)
        """
        self._cancel_flag.clear()

        def _log(msg: str):
            if log_callback:
                try:
                    log_callback(msg)
                except Exception:
                    pass

        def _set_status(status: str):
            if status_callback:
                try:
                    status_callback(status)
                except Exception:
                    pass

        def _notify_completion(success: bool, result: str):
            if completion_callback:
                try:
                    completion_callback(success, result)
                except Exception:
                    pass

        def _cancellable_progress(prog_dict: dict):
            if self._cancel_flag.is_set():
                raise RuntimeError("Download cancelled by user.")
            if progress_callback:
                try:
                    progress_callback(prog_dict)
                except Exception:
                    pass

        def _worker():
            try:
                _set_status("downloading")
                _log(f"Starting download task for URL: {url}")

                if self._cancel_flag.is_set():
                    _log("Download cancelled before start.")
                    _set_status("failed")
                    _notify_completion(False, "Download cancelled by user.")
                    return

                # 1. Detect platform
                _log("Detecting platform...")
                platform = "youtube"
                try:
                    detector = URLDetector()
                    detect_result = detector.detect(url) if hasattr(detector, "detect") else URLDetector.detect(url)
                    if isinstance(detect_result, dict):
                        platform = detect_result.get("platform", "").lower()
                    elif isinstance(detect_result, str):
                        platform = detect_result.lower()
                except Exception as e:
                    _log(f"URL detection note: {e}. Defaulting to generic/youtube platform.")
                    platform = "youtube"

                # Normalize platform alias
                if platform in ["x", "x.com"]:
                    platform = "twitter"
                elif platform in ["yt", "youtu.be"]:
                    platform = "youtube"
                elif platform in ["ig", "instagr.am"]:
                    platform = "instagram"

                if platform not in self.PLATFORM_MODULES:
                    _log(f"Unrecognized platform '{platform}'. Using YouTube/generic engine.")
                    platform = "youtube"

                _log(f"Platform detected: {platform.capitalize()}")

                if self._cancel_flag.is_set():
                    _log("Download cancelled by user.")
                    _set_status("failed")
                    _notify_completion(False, "Download cancelled by user.")
                    return

                # 2. Ensure dependencies for that platform
                _log(f"Verifying dependencies for {platform.capitalize()}...")
                try:
                    self.dep_manager.ensure_platform_deps(platform, log_callback)
                except Exception as e:
                    _log(f"Warning: dependency verification encountered: {e}")

                if self._cancel_flag.is_set():
                    _log("Download cancelled by user.")
                    _set_status("failed")
                    _notify_completion(False, "Download cancelled by user.")
                    return

                # 3. Get ffmpeg path
                ffmpeg_path = ""
                try:
                    ffmpeg_path = self.dep_manager.get_ffmpeg_path(log_callback)
                    if ffmpeg_path:
                        _log(f"FFmpeg binary located at: {ffmpeg_path}")
                    else:
                        _log("FFmpeg binary not explicitly resolved, will rely on system PATH.")
                except Exception as e:
                    _log(f"FFmpeg path check note: {e}")

                if self._cancel_flag.is_set():
                    _log("Download cancelled by user.")
                    _set_status("failed")
                    _notify_completion(False, "Download cancelled by user.")
                    return

                # Ensure output directory exists
                os.makedirs(output_dir, exist_ok=True)

                platform_mod = self.PLATFORM_MODULES.get(platform, youtube)

                # 4. Try primary download
                _log(f"Attempting primary download via {platform.capitalize()} module...")
                downloaded_file = None
                try:
                    downloaded_file = platform_mod.download_primary(
                        url=url,
                        output_dir=output_dir,
                        resolution_key=resolution_key,
                        mode=mode,
                        ffmpeg_path=ffmpeg_path,
                        progress_callback=_cancellable_progress,
                        log_callback=log_callback,
                    )
                except Exception as e:
                    if self._cancel_flag.is_set():
                        _log("Download cancelled during primary attempt.")
                        _set_status("failed")
                        _notify_completion(False, "Download cancelled by user.")
                        return
                    _log(f"Primary download attempt encountered exception: {e}")

                # 5. Check if cancelled
                if self._cancel_flag.is_set():
                    _log("Download cancelled by user.")
                    _set_status("failed")
                    _notify_completion(False, "Download cancelled by user.")
                    return

                # If primary failed, try fallback
                if not downloaded_file or not os.path.exists(downloaded_file):
                    _log("Primary download method failed. Switching to fallback download method...")
                    try:
                        downloaded_file = platform_mod.download_fallback(
                            url=url,
                            output_dir=output_dir,
                            resolution_key=resolution_key,
                            mode=mode,
                            ffmpeg_path=ffmpeg_path,
                            progress_callback=_cancellable_progress,
                            log_callback=log_callback,
                        )
                    except Exception as e:
                        if self._cancel_flag.is_set():
                            _log("Download cancelled during fallback attempt.")
                            _set_status("failed")
                            _notify_completion(False, "Download cancelled by user.")
                            return
                        _log(f"Fallback download attempt encountered exception: {e}")

                # 6. Final status and completion callback
                if self._cancel_flag.is_set():
                    _log("Download cancelled by user.")
                    _set_status("failed")
                    _notify_completion(False, "Download cancelled by user.")
                elif downloaded_file and os.path.exists(downloaded_file):
                    abs_path = os.path.abspath(downloaded_file)
                    _log(f"Download successfully completed: {abs_path}")
                    _set_status("complete")
                    _notify_completion(True, abs_path)
                else:
                    _log("Download failed using both primary and fallback methods.")
                    _set_status("failed")
                    _notify_completion(False, "Download failed using both primary and fallback methods.")

            except Exception as e:
                _log(f"Unexpected engine error: {e}")
                _set_status("failed")
                _notify_completion(False, str(e))

        self._current_thread = threading.Thread(
            target=_worker,
            name="DownloaderEngineWorker",
            daemon=True,
        )
        self._current_thread.start()

    def cancel(self):
        """Signal cancellation."""
        self._cancel_flag.set()

    def is_downloading(self) -> bool:
        """Check if a download worker is currently active."""
        return self._current_thread is not None and self._current_thread.is_alive()
