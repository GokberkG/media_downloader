"""TikTok download module providing primary (yt-dlp watermark-free) and fallback (TikWM, Lovetik, gallery-dl) methods."""

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
                log_callback(f"TikTok progress hook error: {e}")

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
                for ext in [".mp4", ".mkv", ".webm"]:
                    candidate = base + ext
                    if os.path.exists(candidate):
                        return os.path.abspath(candidate)
        except Exception:
            pass

    return None


def _convert_to_mp3(input_file: str, output_dir: str, ffmpeg_path: str, log_callback: Optional[Callable] = None) -> Optional[str]:
    """Convert an existing media file to 320kbps MP3 using FFmpeg."""
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
            log_callback(f"TikTok audio conversion error: {e}")
    return None


def _download_stream_with_progress(media_url: str, dest_path: str, progress_callback: Optional[Callable] = None) -> bool:
    """Download a stream URL in chunks and invoke progress_callback."""
    import requests

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.tiktok.com/",
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
    """Download using yt-dlp with TikTok watermark-free options."""
    try:
        import yt_dlp
    except ImportError:
        if log_callback:
            log_callback("Error: yt-dlp is not installed.")
        return None

    os.makedirs(output_dir, exist_ok=True)
    if log_callback:
        log_callback(f"Starting TikTok primary download with yt-dlp (mode: {mode})...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.tiktok.com/",
    }

    recorded_paths = []

    def _post_hook(d):
        if d.get("status") == "finished":
            fp = d.get("filepath") or d.get("info_dict", {}).get("filepath")
            if fp:
                recorded_paths.append(fp)

    outtmpl = os.path.join(output_dir, "%(title).80s [%(id)s].%(ext)s")

    ydl_opts = {
        "outtmpl": outtmpl,
        "logger": _YtDlpLogger(log_callback),
        "progress_hooks": [_create_progress_hook(progress_callback, log_callback)],
        "postprocessor_hooks": [_post_hook],
        "http_headers": headers,
        "quiet": True,
        "no_warnings": False,
        "noplaylist": True,
        # Prefer watermark-free streams
        "format": "best[format_id!*=watermark]/best" if mode != "audio" else "bestaudio/best",
    }

    if ffmpeg_path:
        ydl_opts["ffmpeg_location"] = ffmpeg_path

    if mode == "audio":
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }]
    else:
        ydl_opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            result_file = _locate_output_file(info, ydl, output_dir, mode, recorded_paths)
            if result_file and os.path.exists(result_file):
                if log_callback:
                    log_callback(f"TikTok primary download successful: {result_file}")
                return result_file
            if log_callback:
                log_callback("TikTok primary download finished but output file could not be located.")
    except Exception as e:
        if log_callback:
            log_callback(f"TikTok primary download error: {e}")

    return None


def download_fallback(url: str, output_dir: str, resolution_key: str, mode: str,
                      ffmpeg_path: str, progress_callback: Callable = None,
                      log_callback: Callable = None) -> Optional[str]:
    """Download using alternative TikTok API hostnames (TikWM, Lovetik) and gallery-dl."""
    os.makedirs(output_dir, exist_ok=True)
    if log_callback:
        log_callback("Starting TikTok fallback download procedure...")

    # Fallback 1: TikWM API endpoints
    tikwm_endpoints = [
        "https://www.tikwm.com/api/",
        "https://tikwm.com/api/",
    ]

    for api_url in tikwm_endpoints:
        if log_callback:
            log_callback(f"Trying TikWM API fallback ({api_url})...")
        try:
            import requests

            req_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            }

            resp = requests.post(api_url, data={"url": url, "hd": 1}, headers=req_headers, timeout=15)
            if resp.status_code == 200:
                res_data = resp.json()
                if res_data.get("code") == 0 and "data" in res_data:
                    data = res_data["data"]
                    video_id = data.get("id", str(int(time.time())))
                    title_raw = data.get("title", f"tiktok_{video_id}")
                    safe_title = re.sub(r'[\\/*?:"<>|]', "_", title_raw).strip()[:80] or f"tiktok_{video_id}"

                    if mode == "audio":
                        audio_url = data.get("music")
                        if audio_url:
                            temp_audio = os.path.join(output_dir, f"{safe_title}_raw.mp3")
                            if _download_stream_with_progress(audio_url, temp_audio, progress_callback):
                                final_mp3 = _convert_to_mp3(temp_audio, output_dir, ffmpeg_path, log_callback)
                                if final_mp3:
                                    if os.path.exists(temp_audio) and final_mp3 != temp_audio:
                                        try:
                                            os.remove(temp_audio)
                                        except OSError:
                                            pass
                                    return final_mp3
                                return os.path.abspath(temp_audio)

                    # Video mode or audio conversion from video
                    video_url = data.get("hdplay") or data.get("play")
                    if video_url:
                        # Ensure protocol
                        if video_url.startswith("//"):
                            video_url = "https:" + video_url

                        dest_file = os.path.join(output_dir, f"{safe_title}.mp4")
                        if _download_stream_with_progress(video_url, dest_file, progress_callback):
                            if mode == "audio":
                                mp3_res = _convert_to_mp3(dest_file, output_dir, ffmpeg_path, log_callback)
                                if mp3_res:
                                    if os.path.exists(dest_file):
                                        try:
                                            os.remove(dest_file)
                                        except OSError:
                                            pass
                                    return mp3_res
                            if log_callback:
                                log_callback(f"TikWM fallback successful: {dest_file}")
                            return os.path.abspath(dest_file)

        except Exception as e:
            if log_callback:
                log_callback(f"TikWM API fallback failed: {e}")

    # Fallback 2: Lovetik alternative API
    if log_callback:
        log_callback("Trying Lovetik API fallback...")
    try:
        import requests

        lovetik_url = "https://lovetik.com/api/ajax/search"
        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }
        resp = requests.post(lovetik_url, data={"query": url}, headers=req_headers, timeout=15)
        if resp.status_code == 200:
            lt_data = resp.json()
            if lt_data.get("status") == "ok":
                links = lt_data.get("links", [])
                target_url = None

                if mode == "audio":
                    for item in links:
                        if item.get("t") == "mp3" and "a" in item:
                            target_url = item["a"]
                            break

                if not target_url:
                    for item in links:
                        # Prefer watermark-free mp4
                        if item.get("t") in ["mp4_nowatermark", "mp4_nowatermark_hd", "mp4"] and "a" in item:
                            target_url = item["a"]
                            break

                if target_url:
                    raw_id = lt_data.get("vid", str(int(time.time())))
                    dest_path = os.path.join(output_dir, f"tiktok_{raw_id}.mp4")
                    if _download_stream_with_progress(target_url, dest_path, progress_callback):
                        if mode == "audio":
                            mp3_res = _convert_to_mp3(dest_path, output_dir, ffmpeg_path, log_callback)
                            if mp3_res:
                                if os.path.exists(dest_path):
                                    try:
                                        os.remove(dest_path)
                                    except OSError:
                                        pass
                                return mp3_res
                        if log_callback:
                            log_callback(f"Lovetik API download successful: {dest_path}")
                        return os.path.abspath(dest_path)
    except Exception as e:
        if log_callback:
            log_callback(f"Lovetik API fallback failed: {e}")

    # Fallback 3: gallery-dl
    if log_callback:
        log_callback("Trying gallery-dl fallback for TikTok...")
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

    return None
