"""Instagram download module providing primary (yt-dlp with cookies) and fallback (instaloader, gallery-dl) methods."""

import glob
import os
import re
import subprocess
import sys
import time
from typing import Callable, Optional


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
                log_callback(f"Instagram progress hook error: {e}")

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
            log_callback(f"Instagram audio conversion error: {e}")
    return None


def download_primary(url: str, output_dir: str, resolution_key: str, mode: str,
                     ffmpeg_path: str, progress_callback: Callable = None,
                     log_callback: Callable = None) -> Optional[str]:
    """Download using yt-dlp with Instagram-compatible options and browser cookies."""
    try:
        import yt_dlp
    except ImportError:
        if log_callback:
            log_callback("Error: yt-dlp is not installed.")
        return None

    os.makedirs(output_dir, exist_ok=True)
    if log_callback:
        log_callback(f"Starting Instagram primary download with yt-dlp (mode: {mode})...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.instagram.com/",
    }

    outtmpl = os.path.join(output_dir, "%(title).80s [%(id)s].%(ext)s")

    # Strategy 1: Attempt standard download with headers
    # Strategy 2: If failed, attempt with browser cookies (chrome, firefox, edge)
    cookie_attempts = [None, "chrome", "firefox", "edge"]

    for browser in cookie_attempts:
        recorded_paths = []

        def _post_hook(d):
            if d.get("status") == "finished":
                fp = d.get("filepath") or d.get("info_dict", {}).get("filepath")
                if fp:
                    recorded_paths.append(fp)

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

        if browser:
            if log_callback:
                log_callback(f"Retrying Instagram yt-dlp with cookies from {browser}...")
            ydl_opts["cookiesfrombrowser"] = (browser, None, None, None)

        if mode == "audio":
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }]
        else:
            ydl_opts["format"] = "bestvideo+bestaudio/best"
            ydl_opts["merge_output_format"] = "mp4"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                result_file = _locate_output_file(info, ydl, output_dir, mode, recorded_paths)
                if result_file and os.path.exists(result_file):
                    if log_callback:
                        log_callback(f"Instagram primary download successful: {result_file}")
                    return result_file
        except Exception as e:
            if log_callback:
                attempt_desc = f"with {browser} cookies" if browser else "standard"
                log_callback(f"Instagram yt-dlp ({attempt_desc}) failed: {e}")
            continue

    return None


def download_fallback(url: str, output_dir: str, resolution_key: str, mode: str,
                      ffmpeg_path: str, progress_callback: Callable = None,
                      log_callback: Callable = None) -> Optional[str]:
    """Download using alternative methods (instaloader first, then gallery-dl)."""
    os.makedirs(output_dir, exist_ok=True)
    if log_callback:
        log_callback("Starting Instagram fallback download procedure...")

    shortcode_match = re.search(r"/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", url)
    shortcode = shortcode_match.group(1) if shortcode_match else None

    # Fallback 1: Try instaloader (for posts/reels)
    if shortcode:
        if log_callback:
            log_callback(f"Trying instaloader fallback for post shortcode: {shortcode}...")
        try:
            import instaloader

            existing_files = set(os.listdir(output_dir))
            L = instaloader.Instaloader(
                dirname_pattern=output_dir,
                filename_pattern=f"{shortcode}_{{target}}",
                download_pictures=True,
                download_videos=True,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False,
                compress_json=False,
                post_metadata_txt_pattern="",
            )

            post = instaloader.Post.from_shortcode(L.context, shortcode)
            L.download_post(post, target=output_dir)

            new_files = [
                os.path.join(output_dir, f)
                for f in os.listdir(output_dir)
                if f not in existing_files and shortcode in f
            ]

            # Look for video or image file
            video_candidates = [f for f in new_files if f.lower().endswith(".mp4")]
            media_candidates = video_candidates or [f for f in new_files if f.lower().endswith((".jpg", ".png", ".webp"))]

            if media_candidates:
                downloaded_file = media_candidates[0]
                if progress_callback:
                    progress_callback({
                        "percentage": 100.0,
                        "speed": "N/A",
                        "eta": "00:00",
                        "downloaded": "",
                        "total": "",
                    })

                if mode == "audio" and downloaded_file.lower().endswith(".mp4"):
                    mp3_res = _convert_to_mp3(downloaded_file, output_dir, ffmpeg_path, log_callback)
                    if mp3_res:
                        return mp3_res

                if log_callback:
                    log_callback(f"Instaloader fallback successful: {downloaded_file}")
                return os.path.abspath(downloaded_file)

        except Exception as e:
            if log_callback:
                log_callback(f"Instaloader fallback failed: {e}")

    # Fallback 2: Try gallery-dl
    if log_callback:
        log_callback("Trying gallery-dl fallback for Instagram...")
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
            # Sort newest first
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
        else:
            if log_callback and proc.stderr:
                log_callback(f"gallery-dl output: {proc.stderr[:200]}")

    except Exception as e:
        if log_callback:
            log_callback(f"gallery-dl fallback failed: {e}")

    # Fallback 3: Direct public embed/page extraction via requests
    if shortcode:
        if log_callback:
            log_callback("Trying Instagram public embed scraping fallback...")
        try:
            import requests

            embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
            req_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            }
            resp = requests.get(embed_url, headers=req_headers, timeout=15)
            if resp.status_code == 200:
                video_url_match = re.search(r'video_url&quot;:&quot;([^&"]+)&quot;', resp.text)
                if not video_url_match:
                    video_url_match = re.search(r'"video_url":"([^"]+)"', resp.text)

                if video_url_match:
                    raw_v_url = video_url_match.group(1).replace(r"\u0026", "&").replace("\\/", "/")
                    target_file = os.path.join(output_dir, f"instagram_{shortcode}.mp4")

                    v_resp = requests.get(raw_v_url, stream=True, headers=req_headers, timeout=30)
                    total_size = int(v_resp.headers.get("content-length", 0))
                    downloaded = 0

                    with open(target_file, "wb") as f:
                        for chunk in v_resp.iter_content(chunk_size=64 * 1024):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if progress_callback and total_size > 0:
                                    pct = round((downloaded / total_size) * 100, 2)
                                    progress_callback({
                                        "percentage": pct,
                                        "speed": "",
                                        "eta": "",
                                        "downloaded": f"{downloaded / (1024*1024):.2f} MB",
                                        "total": f"{total_size / (1024*1024):.2f} MB",
                                    })

                    if os.path.exists(target_file):
                        if mode == "audio":
                            mp3_res = _convert_to_mp3(target_file, output_dir, ffmpeg_path, log_callback)
                            if mp3_res:
                                return mp3_res
                        return os.path.abspath(target_file)
        except Exception as e:
            if log_callback:
                log_callback(f"Public embed fallback failed: {e}")

    return None
