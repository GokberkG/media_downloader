"""Twitter/X download module providing primary (yt-dlp) and fallback (gallery-dl, syndication API, vxtwitter) methods."""

import glob
import os
import re
import subprocess
import sys
import time
from typing import Callable, Optional


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
                log_callback(f"Twitter progress hook error: {e}")

    return hook


def _locate_output_file(info: dict, ydl, output_dir: str, mode: str, recorded_paths: list) -> Optional[str]:
    """Locate downloaded file on disk."""
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
                for ext in [".mp4", ".mkv", ".webm", ".jpg", ".png"]:
                    candidate = base + ext
                    if os.path.exists(candidate):
                        return os.path.abspath(candidate)
        except Exception:
            pass

    return None


def _convert_to_mp3(input_file: str, output_dir: str, ffmpeg_path: str, log_callback: Optional[Callable] = None) -> Optional[str]:
    """Convert an existing video or audio file to 320kbps MP3 using FFmpeg."""
    try:
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        final_mp3 = os.path.join(output_dir, f"{base_name}.mp3")

        cmd = [
            ffmpeg_path or "ffmpeg",
            "-y",
            "-i", input_file,
            "-vn",
            "-b:a", "320k",
            final_mp3,
        ]

        kwargs = {}
        if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        if os.path.exists(final_mp3):
            return os.path.abspath(final_mp3)
    except Exception as e:
        if log_callback:
            log_callback(f"Twitter audio conversion error: {e}")
    return None


def _download_stream_with_progress(media_url: str, dest_path: str, progress_callback: Optional[Callable] = None) -> bool:
    """Download a stream URL in chunks and invoke progress_callback."""
    import requests

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }
    resp = requests.get(media_url, stream=True, headers=headers, timeout=30)
    resp.raise_for_status()

    total_size = int(resp.headers.get("content-length", 0))
    downloaded = 0
    start_time = time.time()

    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    pct = round((downloaded / total_size * 100), 2) if total_size > 0 else 0.0
                    elapsed = time.time() - start_time
                    spd = (downloaded / elapsed) if elapsed > 0 else 0
                    speed_str = f"{spd / (1024 * 1024):.2f} MB/s" if spd > 1024 * 1024 else f"{spd / 1024:.2f} KB/s"
                    eta_sec = int((total_size - downloaded) / spd) if spd > 0 and total_size > 0 else 0
                    m, s = divmod(eta_sec, 60)
                    progress_callback({
                        "percentage": pct,
                        "speed": speed_str,
                        "eta": f"{m:02d}:{s:02d}",
                        "downloaded": f"{downloaded / (1024 * 1024):.2f} MB",
                        "total": f"{total_size / (1024 * 1024):.2f} MB" if total_size > 0 else "",
                    })

    if progress_callback:
        progress_callback({
            "percentage": 100.0,
            "speed": "0 B/s",
            "eta": "00:00",
            "downloaded": f"{downloaded / (1024 * 1024):.2f} MB",
            "total": f"{downloaded / (1024 * 1024):.2f} MB",
        })

    return os.path.exists(dest_path)


def download_primary(url: str, output_dir: str, resolution_key: str, mode: str,
                     ffmpeg_path: str, progress_callback: Callable = None,
                     log_callback: Callable = None) -> Optional[str]:
    """Download using yt-dlp with Twitter/X options."""
    try:
        import yt_dlp
    except ImportError:
        if log_callback:
            log_callback("Error: yt-dlp is not installed.")
        return None

    os.makedirs(output_dir, exist_ok=True)
    if log_callback:
        log_callback(f"Starting Twitter/X primary download with yt-dlp (mode: {mode}, res: {resolution_key})...")

    format_str, sort_str = _get_format_and_sort(resolution_key, mode)
    recorded_paths = []

    def _post_hook(d):
        if d.get("status") == "finished":
            fp = d.get("filepath") or d.get("info_dict", {}).get("filepath")
            if fp:
                recorded_paths.append(fp)

    outtmpl = os.path.join(output_dir, "%(title).80s [%(id)s].%(ext)s")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    ydl_opts = {
        "outtmpl": outtmpl,
        "logger": _YtDlpLogger(log_callback),
        "progress_hooks": [_create_progress_hook(progress_callback, log_callback)],
        "postprocessor_hooks": [_post_hook],
        "http_headers": headers,
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
                    log_callback(f"Twitter primary download successful: {result_file}")
                return result_file
            if log_callback:
                log_callback("Twitter primary download finished but could not locate output file.")
    except Exception as e:
        if log_callback:
            log_callback(f"Twitter primary download error: {e}")

    return None


def download_fallback(url: str, output_dir: str, resolution_key: str, mode: str,
                      ffmpeg_path: str, progress_callback: Callable = None,
                      log_callback: Callable = None) -> Optional[str]:
    """Download using fallback methods: gallery-dl, syndication API, and vxtwitter proxy."""
    os.makedirs(output_dir, exist_ok=True)
    if log_callback:
        log_callback("Starting Twitter/X fallback download procedure...")

    tweet_id_match = re.search(r"status/(\d+)", url)
    tweet_id = tweet_id_match.group(1) if tweet_id_match else None

    # Fallback 1: Try gallery-dl
    if log_callback:
        log_callback("Trying gallery-dl fallback for Twitter...")
    try:
        existing_files = set(glob.glob(os.path.join(output_dir, "**", "*"), recursive=True))

        cmd = [
            sys.executable,
            "-m",
            "gallery_dl",
            "--directory",
            output_dir,
            url,
        ]

        kwargs = {}
        if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **kwargs)

        current_files = set(glob.glob(os.path.join(output_dir, "**", "*"), recursive=True))
        new_files = [f for f in (current_files - existing_files) if os.path.isfile(f)]

        if new_files:
            new_files.sort(key=os.path.getmtime, reverse=True)
            chosen_file = new_files[0]

            if progress_callback:
                progress_callback({
                    "percentage": 100.0,
                    "speed": "N/A",
                    "eta": "00:00",
                    "downloaded": "",
                    "total": "",
                })

            if mode == "audio" and chosen_file.lower().endswith(".mp4"):
                mp3_res = _convert_to_mp3(chosen_file, output_dir, ffmpeg_path, log_callback)
                if mp3_res:
                    return mp3_res

            if log_callback:
                log_callback(f"gallery-dl fallback successful: {chosen_file}")
            return os.path.abspath(chosen_file)
    except Exception as e:
        if log_callback:
            log_callback(f"gallery-dl fallback failed: {e}")

    # Fallback 2: Twitter Syndication endpoint
    if tweet_id:
        if log_callback:
            log_callback(f"Trying syndication endpoint fallback for tweet ID {tweet_id}...")
        try:
            import requests

            syndication_url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&lang=en"
            req_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Origin": "https://platform.twitter.com",
                "Referer": "https://platform.twitter.com/",
            }

            resp = requests.get(syndication_url, headers=req_headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                variants = []

                # Look in mediaDetails
                media_details = data.get("mediaDetails", [])
                for media in media_details:
                    video_info = media.get("video_info", {})
                    variants.extend(video_info.get("variants", []))

                # Also check direct video object
                if "video" in data:
                    variants.extend(data["video"].get("variants", []))

                # Filter mp4 variants
                mp4_variants = [v for v in variants if v.get("content_type") == "video/mp4" and "url" in v]
                if mp4_variants:
                    # Sort by bitrate descending
                    mp4_variants.sort(key=lambda x: x.get("bitrate", 0), reverse=True)
                    target_variant = mp4_variants[0]
                    video_url = target_variant["url"]

                    temp_dest = os.path.join(output_dir, f"twitter_{tweet_id}.mp4")
                    if _download_stream_with_progress(video_url, temp_dest, progress_callback):
                        if mode == "audio":
                            mp3_res = _convert_to_mp3(temp_dest, output_dir, ffmpeg_path, log_callback)
                            if mp3_res:
                                if os.path.exists(temp_dest):
                                    try:
                                        os.remove(temp_dest)
                                    except OSError:
                                        pass
                                return mp3_res

                        if log_callback:
                            log_callback(f"Syndication endpoint download successful: {temp_dest}")
                        return os.path.abspath(temp_dest)
        except Exception as e:
            if log_callback:
                log_callback(f"Syndication endpoint fallback failed: {e}")

    # Fallback 3: VxTwitter proxy
    if tweet_id:
        if log_callback:
            log_callback(f"Trying VxTwitter proxy fallback for tweet ID {tweet_id}...")
        try:
            import requests

            vx_urls = [
                f"https://api.vxtwitter.com/status/{tweet_id}",
                f"https://api.vxtwitter.com/Twitter/status/{tweet_id}",
            ]

            req_headers = {
                "User-Agent": "Mozilla/5.0",
            }

            for vx_url in vx_urls:
                resp = requests.get(vx_url, headers=req_headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    media_urls = data.get("mediaURLs", [])
                    media_ext = data.get("media_extended", [])

                    video_candidates = []
                    for ext_item in media_ext:
                        if ext_item.get("type") == "video" and "url" in ext_item:
                            video_candidates.append(ext_item["url"])

                    for m_url in media_urls:
                        if ".mp4" in m_url.lower():
                            video_candidates.append(m_url)

                    if video_candidates:
                        chosen_v_url = video_candidates[0]
                        temp_dest = os.path.join(output_dir, f"twitter_vx_{tweet_id}.mp4")
                        if _download_stream_with_progress(chosen_v_url, temp_dest, progress_callback):
                            if mode == "audio":
                                mp3_res = _convert_to_mp3(temp_dest, output_dir, ffmpeg_path, log_callback)
                                if mp3_res:
                                    if os.path.exists(temp_dest):
                                        try:
                                            os.remove(temp_dest)
                                        except OSError:
                                            pass
                                    return mp3_res

                            if log_callback:
                                log_callback(f"VxTwitter proxy download successful: {temp_dest}")
                            return os.path.abspath(temp_dest)
        except Exception as e:
            if log_callback:
                log_callback(f"VxTwitter proxy fallback failed: {e}")

    return None
