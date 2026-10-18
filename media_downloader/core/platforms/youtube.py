"""YouTube download module providing primary (yt-dlp) and fallback (player_clients, pytubefix) methods."""

import os
import re
import subprocess
import time
from typing import Callable, Optional


def _extract_res_int(stream) -> int:
    """Extract integer resolution from a stream object."""
    if hasattr(stream, "resolution_int") and stream.resolution_int is not None:
        try:
            return int(stream.resolution_int)
        except (ValueError, TypeError):
            pass
    res_str = getattr(stream, "resolution", None)
    if res_str:
        digits = "".join(c for c in str(res_str) if c.isdigit())
        if digits:
            return int(digits)
    return 0


def _get_target_height(resolution_key: str) -> int:
    """Get target height integer from resolution key or ResolutionSelector."""
    try:
        from core.resolution_selector import ResolutionSelector

        try:
            return ResolutionSelector.get_target_height(resolution_key)
        except (TypeError, AttributeError):
            return ResolutionSelector().get_target_height(resolution_key)
    except Exception:
        pass
    digits = "".join(c for c in resolution_key if c.isdigit())
    return int(digits) if digits else 1080


def _get_format_and_sort(resolution_key: str, mode: str):
    """Retrieve format string and format sort for yt-dlp."""
    format_str = None
    sort_str = None
    try:
        from core.resolution_selector import ResolutionSelector

        try:
            format_str = ResolutionSelector.get_ytdlp_format_string(resolution_key, mode)
        except (TypeError, AttributeError):
            format_str = ResolutionSelector().get_ytdlp_format_string(resolution_key, mode)

        try:
            sort_str = ResolutionSelector.get_ytdlp_sort_string(resolution_key)
        except (TypeError, AttributeError):
            sort_str = ResolutionSelector().get_ytdlp_sort_string(resolution_key)
    except Exception:
        pass

    if not format_str:
        if mode == "audio":
            format_str = "bestaudio/best"
        else:
            height = _get_target_height(resolution_key)
            format_str = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"

    if not sort_str and mode == "video":
        height = _get_target_height(resolution_key)
        sort_str = f"res:{height}"

    return format_str, sort_str


class _YtDlpLogger:
    """Custom logger routing yt-dlp logs to log_callback."""

    def __init__(self, log_callback: Optional[Callable]):
        self.log_callback = log_callback

    def debug(self, msg: str):
        pass

    def info(self, msg: str):
        if self.log_callback and msg and not msg.startswith("[download]"):
            self.log_callback(msg)

    def warning(self, msg: str):
        if self.log_callback and msg:
            self.log_callback(f"[Warning] {msg}")

    def error(self, msg: str):
        if self.log_callback and msg:
            self.log_callback(f"[Error] {msg}")


def _create_progress_hook(progress_callback: Optional[Callable], log_callback: Optional[Callable] = None):
    """Create a progress hook function matching the standardized progress dict interface."""

    def hook(d: dict):
        if not progress_callback:
            return
        try:
            status = d.get("status", "")
            if status == "downloading":
                downloaded = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                pct = 0.0
                if total > 0:
                    pct = round((downloaded / total) * 100, 2)
                elif "_percent_str" in d:
                    clean = re.sub(r"\x1b\[[0-9;]*m", "", str(d["_percent_str"])).replace("%", "").strip()
                    try:
                        pct = round(float(clean), 2)
                    except ValueError:
                        pct = 0.0

                speed_str = d.get("_speed_str", "")
                if not speed_str and d.get("speed"):
                    spd = d["speed"]
                    if spd >= 1024 * 1024:
                        speed_str = f"{spd / (1024 * 1024):.2f} MB/s"
                    elif spd >= 1024:
                        speed_str = f"{spd / 1024:.2f} KB/s"
                    else:
                        speed_str = f"{spd:.1f} B/s"

                eta_str = d.get("_eta_str", "")
                if not eta_str and d.get("eta") is not None:
                    eta_sec = int(d["eta"])
                    m, s = divmod(eta_sec, 60)
                    h, m = divmod(m, 60)
                    eta_str = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

                down_str = d.get("_downloaded_bytes_str", "")
                if not down_str and downloaded:
                    down_str = f"{downloaded / (1024 * 1024):.2f} MB"

                tot_str = d.get("_total_bytes_str") or d.get("_total_bytes_estimate_str", "")
                if not tot_str and total:
                    tot_str = f"{total / (1024 * 1024):.2f} MB"

                progress_callback({
                    "percentage": float(pct),
                    "speed": str(speed_str).strip(),
                    "eta": str(eta_str).strip(),
                    "downloaded": str(down_str).strip(),
                    "total": str(tot_str).strip(),
                })
            elif status == "finished":
                total = d.get("total_bytes") or d.get("downloaded_bytes", 0)
                tot_str = f"{total / (1024 * 1024):.2f} MB" if total else ""
                progress_callback({
                    "percentage": 100.0,
                    "speed": "0 B/s",
                    "eta": "00:00",
                    "downloaded": tot_str,
                    "total": tot_str,
                })
        except Exception as e:
            if log_callback:
                log_callback(f"YouTube progress hook error: {e}")

    return hook


def _locate_output_file(info: dict, ydl, output_dir: str, mode: str, recorded_paths: list) -> Optional[str]:
    """Locate the downloaded and post-processed file on disk."""
    for p in reversed(recorded_paths):
        if p and os.path.exists(p):
            return os.path.abspath(p)

    if info and "requested_downloads" in info:
        for rd in info["requested_downloads"]:
            p = rd.get("filepath")
            if p and os.path.exists(p):
                return os.path.abspath(p)

    if info:
        try:
            target_entry = info["entries"][0] if "entries" in info and info["entries"] else info
            prep = ydl.prepare_filename(target_entry)
            if os.path.exists(prep):
                return os.path.abspath(prep)
            base, _ = os.path.splitext(prep)
            if mode == "audio":
                for ext in [".mp3", ".m4a", ".opus", ".aac"]:
                    candidate = base + ext
                    if os.path.exists(candidate):
                        return os.path.abspath(candidate)
            else:
                for ext in [".mp4", ".mkv", ".webm"]:
                    candidate = base + ext
                    if os.path.exists(candidate):
                        return os.path.abspath(candidate)
        except Exception:
            pass

    return None


def download_primary(url: str, output_dir: str, resolution_key: str, mode: str,
                     ffmpeg_path: str, progress_callback: Callable = None,
                     log_callback: Callable = None) -> Optional[str]:
    """Download using yt-dlp (primary method).
    
    Args:
        url: Video URL
        output_dir: Download directory
        resolution_key: '1080p', '720p', '2160p', etc.
        mode: 'video' or 'audio'
        ffmpeg_path: Path to ffmpeg binary
        progress_callback: Called with progress dict
        log_callback: Called with log messages
    
    Returns:
        Path to downloaded file or None on failure
    """
    try:
        import yt_dlp
    except ImportError:
        if log_callback:
            log_callback("Error: yt-dlp is not installed.")
        return None

    os.makedirs(output_dir, exist_ok=True)
    if log_callback:
        log_callback(f"Starting YouTube primary download with yt-dlp (mode: {mode}, resolution: {resolution_key})...")

    format_str, sort_str = _get_format_and_sort(resolution_key, mode)
    recorded_paths = []

    def _post_hook(d):
        if d.get("status") == "finished":
            fp = d.get("filepath") or d.get("info_dict", {}).get("filepath")
            if fp:
                recorded_paths.append(fp)

    outtmpl = os.path.join(output_dir, "%(title).100s [%(id)s].%(ext)s")

    ydl_opts = {
        "outtmpl": outtmpl,
        "logger": _YtDlpLogger(log_callback),
        "progress_hooks": [_create_progress_hook(progress_callback, log_callback)],
        "postprocessor_hooks": [_post_hook],
        "quiet": True,
        "no_warnings": False,
        "noplaylist": True,
    }

    if ffmpeg_path:
        ydl_opts["ffmpeg_location"] = ffmpeg_path

    if mode == "audio":
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }]
    else:
        ydl_opts["format"] = format_str
        if sort_str:
            ydl_opts["format_sort"] = [sort_str] if isinstance(sort_str, str) else sort_str
        ydl_opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            result_file = _locate_output_file(info, ydl, output_dir, mode, recorded_paths)
            if result_file and os.path.exists(result_file):
                if log_callback:
                    log_callback(f"YouTube primary download successful: {result_file}")
                return result_file
            if log_callback:
                log_callback("YouTube primary download completed but output file could not be located.")
            return None
    except Exception as e:
        if log_callback:
            log_callback(f"YouTube primary download error: {e}")
        return None


def download_fallback(url: str, output_dir: str, resolution_key: str, mode: str,
                      ffmpeg_path: str, progress_callback: Callable = None,
                      log_callback: Callable = None) -> Optional[str]:
    """Download using alternative methods (fallback).
    
    1. Tries yt-dlp with alternative player_client values: android, ios, tv_embedded, web_embedded.
    2. If yt-dlp clients fail, uses pytubefix.
    """
    os.makedirs(output_dir, exist_ok=True)
    if log_callback:
        log_callback("Starting YouTube fallback download procedure...")

    # Stage 1: Try alternative yt-dlp player clients
    player_clients = ["android", "ios", "tv_embedded", "web_embedded"]
    try:
        import yt_dlp

        format_str, sort_str = _get_format_and_sort(resolution_key, mode)
        for client in player_clients:
            if log_callback:
                log_callback(f"YouTube fallback: trying yt-dlp player_client '{client}'...")

            recorded_paths = []

            def _post_hook(d):
                if d.get("status") == "finished":
                    fp = d.get("filepath") or d.get("info_dict", {}).get("filepath")
                    if fp:
                        recorded_paths.append(fp)

            outtmpl = os.path.join(output_dir, "%(title).100s [%(id)s].%(ext)s")
            ydl_opts = {
                "outtmpl": outtmpl,
                "logger": _YtDlpLogger(log_callback),
                "progress_hooks": [_create_progress_hook(progress_callback, log_callback)],
                "postprocessor_hooks": [_post_hook],
                "quiet": True,
                "no_warnings": False,
                "noplaylist": True,
                "extractor_args": {
                    "youtube": {
                        "player_client": [client]
                    }
                },
            }

            if ffmpeg_path:
                ydl_opts["ffmpeg_location"] = ffmpeg_path

            if mode == "audio":
                ydl_opts["format"] = "bestaudio/best"
                ydl_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }]
            else:
                ydl_opts["format"] = format_str
                if sort_str:
                    ydl_opts["format_sort"] = [sort_str] if isinstance(sort_str, str) else sort_str
                ydl_opts["merge_output_format"] = "mp4"

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    result_file = _locate_output_file(info, ydl, output_dir, mode, recorded_paths)
                    if result_file and os.path.exists(result_file):
                        if log_callback:
                            log_callback(f"YouTube fallback successful with client '{client}': {result_file}")
                        return result_file
            except Exception as e:
                if log_callback:
                    log_callback(f"YouTube fallback with client '{client}' failed: {e}")
                continue
    except ImportError:
        if log_callback:
            log_callback("yt-dlp is not available for fallback clients.")

    # Stage 2: pytubefix fallback
    if log_callback:
        log_callback("All yt-dlp client fallbacks failed. Trying pytubefix fallback...")

    try:
        from pytubefix import YouTube

        def pytubefix_progress(stream, chunk, bytes_remaining):
            if progress_callback:
                try:
                    total = getattr(stream, "filesize", 0) or 0
                    downloaded = total - bytes_remaining
                    pct = round((downloaded / total * 100), 2) if total > 0 else 0.0
                    progress_callback({
                        "percentage": float(pct),
                        "speed": "",
                        "eta": "",
                        "downloaded": f"{downloaded / (1024 * 1024):.2f} MB" if total > 0 else "",
                        "total": f"{total / (1024 * 1024):.2f} MB" if total > 0 else "",
                    })
                except Exception:
                    pass

        yt = YouTube(url, on_progress_callback=pytubefix_progress)
        raw_title = getattr(yt, "title", "youtube_media") or "youtube_media"
        safe_title = re.sub(r'[\\/*?:"<>|]', "_", raw_title).strip()
        if not safe_title:
            safe_title = f"youtube_media_{int(time.time())}"

        subprocess_kwargs = {}
        if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            subprocess_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        ffmpeg_bin = ffmpeg_path or "ffmpeg"

        if mode == "audio":
            if log_callback:
                log_callback("pytubefix: extracting audio stream...")
            audio_stream = yt.streams.get_audio_only() or yt.streams.filter(only_audio=True).first()
            if not audio_stream:
                if log_callback:
                    log_callback("pytubefix: No audio stream found.")
                return None

            temp_audio_name = f"temp_aud_{int(time.time())}.m4a"
            raw_audio_path = audio_stream.download(output_path=output_dir, filename=temp_audio_name)

            final_mp3 = os.path.join(output_dir, f"{safe_title}.mp3")
            cmd = [
                ffmpeg_bin,
                "-y",
                "-i", raw_audio_path,
                "-vn",
                "-b:a", "320k",
                final_mp3,
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **subprocess_kwargs)

            if os.path.exists(raw_audio_path):
                try:
                    os.remove(raw_audio_path)
                except OSError:
                    pass

            if os.path.exists(final_mp3):
                if log_callback:
                    log_callback(f"pytubefix audio download successful: {final_mp3}")
                return os.path.abspath(final_mp3)

        else:
            # Video mode
            target_height = _get_target_height(resolution_key)
            if log_callback:
                log_callback(f"pytubefix: selecting video stream closest to target height {target_height}p...")

            video_streams = yt.streams.filter(type="video")
            if not video_streams:
                if log_callback:
                    log_callback("pytubefix: No video streams found.")
                return None

            def _stream_diff(st):
                res_int = _extract_res_int(st)
                return abs(res_int - target_height) if res_int > 0 else 99999

            chosen_video = min(video_streams, key=_stream_diff)
            if log_callback:
                log_callback(f"pytubefix: selected stream resolution {getattr(chosen_video, 'resolution', 'unknown')}")

            if getattr(chosen_video, "is_progressive", False):
                # Contains both video and audio
                final_name = f"{safe_title}.mp4"
                downloaded = chosen_video.download(output_path=output_dir, filename=final_name)
                if downloaded and os.path.exists(downloaded):
                    if log_callback:
                        log_callback(f"pytubefix progressive video download successful: {downloaded}")
                    return os.path.abspath(downloaded)
            else:
                # Video-only adaptive stream: download audio and merge
                temp_vid_name = f"temp_vid_{int(time.time())}.mp4"
                temp_vid_path = chosen_video.download(output_path=output_dir, filename=temp_vid_name)

                audio_stream = yt.streams.get_audio_only() or yt.streams.filter(only_audio=True).first()
                temp_aud_path = None
                if audio_stream:
                    temp_aud_name = f"temp_aud_{int(time.time())}.m4a"
                    temp_aud_path = audio_stream.download(output_path=output_dir, filename=temp_aud_name)

                final_vid = os.path.join(output_dir, f"{safe_title}.mp4")

                if temp_aud_path and os.path.exists(temp_aud_path):
                    cmd = [
                        ffmpeg_bin,
                        "-y",
                        "-i", temp_vid_path,
                        "-i", temp_aud_path,
                        "-c:v", "copy",
                        "-c:a", "aac",
                        final_vid,
                    ]
                else:
                    cmd = [
                        ffmpeg_bin,
                        "-y",
                        "-i", temp_vid_path,
                        "-c:v", "copy",
                        final_vid,
                    ]

                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **subprocess_kwargs)

                for tmp in [temp_vid_path, temp_aud_path]:
                    if tmp and os.path.exists(tmp):
                        try:
                            os.remove(tmp)
                        except OSError:
                            pass

                if os.path.exists(final_vid):
                    if log_callback:
                        log_callback(f"pytubefix video download successful: {final_vid}")
                    return os.path.abspath(final_vid)

    except Exception as e:
        if log_callback:
            log_callback(f"pytubefix fallback failed: {e}")

    return None
