"""Main application window for Media Downloader."""
import datetime
import os
import subprocess
import sys
import tkinter
from tkinter import filedialog, messagebox
import customtkinter

# Import core modules and translations with resilient fallbacks
try:
    from locales.translations import get_text, TRANSLATIONS
except ImportError:
    get_text = None
    TRANSLATIONS = None

try:
    from core.config_manager import ConfigManager
except ImportError:
    ConfigManager = None

try:
    from core.url_detector import URLDetector
except ImportError:
    URLDetector = None

try:
    from core.downloader_engine import DownloaderEngine
except ImportError:
    DownloaderEngine = None

try:
    from core.resolution_selector import ResolutionSelector
except ImportError:
    ResolutionSelector = None


# Comprehensive multilingual fallback dictionary
DEFAULT_TEXTS = {
    "tr": {
        "app_title": "Medya İndirici",
        "app_subtitle": "YouTube, Instagram, TikTok & X",
        "language": "Dil",
        "theme": "Tema",
        "theme_system": "Sistem",
        "theme_dark": "Karanlık",
        "theme_light": "Aydınlık",
        "format": "Format",
        "format_video": "Video (MP4)",
        "format_audio": "Ses (MP3)",
        "resolution": "Çözünürlük",
        "resolution_1080p": "1080p (Varsayılan)",
        "resolution_4k": "2160p (4K)",
        "resolution_2k": "1440p (2K)",
        "resolution_720p": "720p (HD)",
        "resolution_480p": "480p",
        "resolution_360p": "360p",
        "resolution_best": "En Yüksek Kalite",
        "url_label": "Medya Bağlantısı (URL)",
        "url_placeholder": "https://www.youtube.com/watch?v=... veya Instagram, TikTok, X bağlantısı yapıştırın",
        "btn_paste": "Yapıştır",
        "platform_label": "Platform:",
        "content_type_label": "Tür:",
        "platform_unknown": "Algılanamadı",
        "folder_label": "İndirme Klasörü",
        "btn_browse": "Gözat...",
        "btn_download": "İndirmeyi Başlat",
        "btn_cancel": "İptal Et",
        "btn_open_folder": "Klasörü Aç",
        "progress_label": "Durum",
        "speed": "Hız",
        "eta": "Kalan Süre",
        "engine": "Motor",
        "status_ready": "Hazır",
        "status_downloading": "İndiriliyor...",
        "status_completed": "Tamamlandı",
        "status_failed": "Başarısız Oldu",
        "status_cancelled": "İptal Edildi",
        "log_title": "İşlem Günlüğü",
        "btn_clear_log": "Temizle",
        "err_invalid_url": "Lütfen geçerli bir indirme bağlantısı girin.",
        "download_started": "İndirme başlatıldı: {url}",
        "download_finished": "Dosya başarıyla indirildi: {path}",
    },
    "en": {
        "app_title": "Media Downloader",
        "app_subtitle": "YouTube, Instagram, TikTok & X",
        "language": "Language",
        "theme": "Theme",
        "theme_system": "System",
        "theme_dark": "Dark",
        "theme_light": "Light",
        "format": "Format",
        "format_video": "Video (MP4)",
        "format_audio": "Audio (MP3)",
        "resolution": "Resolution",
        "resolution_1080p": "1080p (Default)",
        "resolution_4k": "2160p (4K)",
        "resolution_2k": "1440p (2K)",
        "resolution_720p": "720p (HD)",
        "resolution_480p": "480p",
        "resolution_360p": "360p",
        "resolution_best": "Best Quality",
        "url_label": "Media URL",
        "url_placeholder": "Paste YouTube, Instagram, TikTok, or X link here...",
        "btn_paste": "Paste",
        "platform_label": "Platform:",
        "content_type_label": "Type:",
        "platform_unknown": "Unknown",
        "folder_label": "Download Folder",
        "btn_browse": "Browse...",
        "btn_download": "Start Download",
        "btn_cancel": "Cancel",
        "btn_open_folder": "Open Folder",
        "progress_label": "Status",
        "speed": "Speed",
        "eta": "ETA",
        "engine": "Engine",
        "status_ready": "Ready",
        "status_downloading": "Downloading...",
        "status_completed": "Completed",
        "status_failed": "Failed",
        "status_cancelled": "Cancelled",
        "log_title": "Process Log",
        "btn_clear_log": "Clear",
        "err_invalid_url": "Please enter a valid media URL.",
        "download_started": "Download started: {url}",
        "download_finished": "File downloaded successfully: {path}",
    },
    "de": {
        "app_title": "Medien-Downloader",
        "app_subtitle": "YouTube, Instagram, TikTok & X",
        "language": "Sprache",
        "theme": "Design",
        "theme_system": "System",
        "theme_dark": "Dunkel",
        "theme_light": "Hell",
        "format": "Format",
        "format_video": "Video (MP4)",
        "format_audio": "Audio (MP3)",
        "resolution": "Auflösung",
        "resolution_1080p": "1080p (Standard)",
        "resolution_4k": "2160p (4K)",
        "resolution_2k": "1440p (2K)",
        "resolution_720p": "720p (HD)",
        "resolution_480p": "480p",
        "resolution_360p": "360p",
        "resolution_best": "Beste Qualität",
        "url_label": "Medien-URL",
        "url_placeholder": "YouTube, Instagram, TikTok oder X Link hier einfügen...",
        "btn_paste": "Einfügen",
        "platform_label": "Plattform:",
        "content_type_label": "Typ:",
        "platform_unknown": "Unbekannt",
        "folder_label": "Download-Ordner",
        "btn_browse": "Durchsuchen...",
        "btn_download": "Download Starten",
        "btn_cancel": "Abbrechen",
        "btn_open_folder": "Ordner Öffnen",
        "progress_label": "Status",
        "speed": "Geschwindigkeit",
        "eta": "Verbleibend",
        "engine": "Engine",
        "status_ready": "Bereit",
        "status_downloading": "Wird heruntergeladen...",
        "status_completed": "Abgeschlossen",
        "status_failed": "Fehlgeschlagen",
        "status_cancelled": "Abgebrochen",
        "log_title": "Prozessprotokoll",
        "btn_clear_log": "Löschen",
        "err_invalid_url": "Bitte geben Sie eine gültige Medien-URL ein.",
        "download_started": "Download gestartet: {url}",
        "download_finished": "Datei erfolgreich heruntergeladen: {path}",
    },
}

LANG_CODE_MAP = {"Türkçe": "tr", "English": "en", "Deutsch": "de"}
LANG_NAME_MAP = {"tr": "Türkçe", "en": "English", "de": "Deutsch"}

RESOLUTION_MAPPING = [
    ("resolution_1080p", "1080p"),
    ("resolution_4k", "2160p"),
    ("resolution_2k", "1440p"),
    ("resolution_720p", "720p"),
    ("resolution_480p", "480p"),
    ("resolution_360p", "360p"),
    ("resolution_best", "best"),
]

THEME_MAPPING = [
    ("theme_system", "system"),
    ("theme_dark", "dark"),
    ("theme_light", "light"),
]


class FallbackConfigManager:
    """In-memory fallback configuration manager."""

    def __init__(self):
        self._data = {
            "language": "tr",
            "theme": "system",
            "window_geometry": "800x700",
            "download_dir": os.path.join(os.path.expanduser("~"), "Downloads"),
            "resolution": "1080p",
            "format": "video",
        }

    def load(self):
        return self._data

    def save(self):
        pass

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value


class FallbackURLDetector:
    """Fallback detector for media platforms."""

    @classmethod
    def detect(cls, url: str) -> dict:
        url_lower = (url or "").lower().strip()
        platform = None
        content_type = None

        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            platform = "youtube"
            content_type = "Shorts" if "/shorts/" in url_lower else "Video"
        elif "instagram.com" in url_lower:
            platform = "instagram"
            content_type = "Reels" if "/reel/" in url_lower or "/reels/" in url_lower else "Post"
        elif "twitter.com" in url_lower or "x.com" in url_lower:
            platform = "twitter"
            content_type = "Tweet"
        elif "tiktok.com" in url_lower:
            platform = "tiktok"
            content_type = "Video"

        return {"platform": platform, "content_type": content_type, "url": url}


class MediaDownloaderApp(customtkinter.CTk):
    """Main application window for Media Downloader."""

    def __init__(self):
        super().__init__()

        # Initialize config manager
        if ConfigManager is not None:
            try:
                self.config = ConfigManager()
                self.config.load()
            except Exception:
                self.config = FallbackConfigManager()
        else:
            self.config = FallbackConfigManager()

        # Load preferences
        self.current_lang = self.config.get("language", "tr")
        if self.current_lang not in ("tr", "en", "de"):
            self.current_lang = "tr"

        self.current_theme = self.config.get("theme", "system")
        if self.current_theme not in ("system", "dark", "light"):
            self.current_theme = "system"

        self.selected_format = self.config.get("format", "video")
        if self.selected_format not in ("video", "audio"):
            self.selected_format = "video"

        self.selected_resolution_key = self.config.get("resolution", "1080p")

        saved_download_dir = self.config.get(
            "download_dir",
            os.path.join(os.path.expanduser("~"), "Downloads"),
        )
        if not saved_download_dir:
            saved_download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        self.download_dir = saved_download_dir

        # Initialize DownloaderEngine
        if DownloaderEngine is not None:
            try:
                self.engine = DownloaderEngine()
            except Exception as e:
                print(f"Error instantiating DownloaderEngine: {e}")
                self.engine = None
        else:
            self.engine = None

        # Tracking state
        self.current_speed = "-"
        self.current_eta = "-"
        self.current_engine = "-"
        self.display_to_res_key = {}
        self.res_key_to_display = {}
        self.display_to_theme = {}
        self.theme_to_display = {}
        self.video_display_str = "Video (MP4)"
        self.audio_display_str = "Audio (MP3)"

        # Window configuration
        self.title(self._t("app_title"))
        self.minsize(700, 600)

        # Restore window geometry
        saved_geometry = self.config.get("window_geometry", "800x700")
        try:
            self.geometry(saved_geometry)
        except Exception:
            self.geometry("800x700")

        # Apply theme
        customtkinter.set_appearance_mode(self.current_theme)
        customtkinter.set_default_color_theme("blue")

        # Load window icon
        self._load_app_icon()

        # Setup GUI components
        self._setup_ui()

        # Refresh all localized text
        self._refresh_ui_texts()

        # Handle window close protocol
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _load_app_icon(self):
        """Load or generate application icon."""
        try:
            assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
            icon_path = os.path.join(assets_dir, "icon.ico")
            if not os.path.exists(icon_path):
                try:
                    from assets.icon import generate_icon
                    generate_icon()
                except Exception:
                    pass

            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

    def _t(self, key: str, **kwargs) -> str:
        """Fetch localized string with fallback mechanism."""
        val = None
        if get_text is not None:
            try:
                val = get_text(key, self.current_lang)
            except Exception:
                val = None

        if not val or val == key:
            lang_dict = DEFAULT_TEXTS.get(self.current_lang, DEFAULT_TEXTS.get("en", {}))
            val = lang_dict.get(key, DEFAULT_TEXTS.get("en", {}).get(key, key))

        if kwargs and isinstance(val, str):
            try:
                val = val.format(**kwargs)
            except Exception:
                pass
        return str(val)

    def _setup_ui(self):
        """Construct the UI layout."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Main scrollable or root container
        self.main_container = customtkinter.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=0, sticky="nsew", padx=18, pady=14)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(6, weight=1)  # Log panel expands

        # ==============================================================
        # 1. Header Frame (Top bar)
        # ==============================================================
        self.header_frame = customtkinter.CTkFrame(self.main_container, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.header_frame.grid_columnconfigure(0, weight=1)

        # Left title info
        self.title_box = customtkinter.CTkFrame(self.header_frame, fg_color="transparent")
        self.title_box.grid(row=0, column=0, sticky="w")

        self.lbl_title = customtkinter.CTkLabel(
            self.title_box,
            text=self._t("app_title"),
            font=customtkinter.CTkFont(family="Segoe UI", size=20, weight="bold"),
        )
        self.lbl_title.pack(anchor="w")

        self.lbl_subtitle = customtkinter.CTkLabel(
            self.title_box,
            text=self._t("app_subtitle"),
            font=customtkinter.CTkFont(family="Segoe UI", size=11),
            text_color=("gray40", "gray60"),
        )
        self.lbl_subtitle.pack(anchor="w")

        # Right control widgets: Language & Theme dropdowns
        self.top_controls = customtkinter.CTkFrame(self.header_frame, fg_color="transparent")
        self.top_controls.grid(row=0, column=1, sticky="e")

        self.lang_menu = customtkinter.CTkOptionMenu(
            self.top_controls,
            values=["Türkçe", "English", "Deutsch"],
            width=110,
            height=32,
            font=customtkinter.CTkFont(family="Segoe UI", size=12),
            command=self._on_language_change,
        )
        self.lang_menu.pack(side="left", padx=(0, 8))

        self.theme_menu = customtkinter.CTkOptionMenu(
            self.top_controls,
            values=["Sistem", "Karanlık", "Aydınlık"],
            width=110,
            height=32,
            font=customtkinter.CTkFont(family="Segoe UI", size=12),
            command=self._on_theme_change,
        )
        self.theme_menu.pack(side="left")

        # ==============================================================
        # 2 & 3. Format & Resolution Frame
        # ==============================================================
        self.options_frame = customtkinter.CTkFrame(self.main_container, corner_radius=10)
        self.options_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.options_frame.grid_columnconfigure(0, weight=1)
        self.options_frame.grid_columnconfigure(1, weight=1)

        # Format column (left)
        self.format_subframe = customtkinter.CTkFrame(self.options_frame, fg_color="transparent")
        self.format_subframe.grid(row=0, column=0, sticky="ew", padx=14, pady=10)

        self.lbl_format = customtkinter.CTkLabel(
            self.format_subframe,
            text=self._t("format"),
            font=customtkinter.CTkFont(family="Segoe UI", size=13, weight="bold"),
        )
        self.lbl_format.pack(anchor="w", pady=(0, 5))

        self.format_segmented_btn = customtkinter.CTkSegmentedButton(
            self.format_subframe,
            values=["Video (MP4)", "Audio (MP3)"],
            height=34,
            font=customtkinter.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._on_format_change,
        )
        self.format_segmented_btn.pack(fill="x")

        # Resolution column (right)
        self.resolution_subframe = customtkinter.CTkFrame(self.options_frame, fg_color="transparent")
        self.resolution_subframe.grid(row=0, column=1, sticky="ew", padx=14, pady=10)

        self.lbl_resolution = customtkinter.CTkLabel(
            self.resolution_subframe,
            text=self._t("resolution"),
            font=customtkinter.CTkFont(family="Segoe UI", size=13, weight="bold"),
        )
        self.lbl_resolution.pack(anchor="w", pady=(0, 5))

        self.resolution_menu = customtkinter.CTkOptionMenu(
            self.resolution_subframe,
            values=["1080p (Varsayılan)"],
            height=34,
            font=customtkinter.CTkFont(family="Segoe UI", size=12),
            command=self._on_resolution_change,
        )
        self.resolution_menu.pack(fill="x")

        # ==============================================================
        # 4. URL Input & Platform Detection Frame
        # ==============================================================
        self.url_frame = customtkinter.CTkFrame(self.main_container, corner_radius=10)
        self.url_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.url_frame.grid_columnconfigure(0, weight=1)

        # URL label
        self.lbl_url = customtkinter.CTkLabel(
            self.url_frame,
            text=self._t("url_label"),
            font=customtkinter.CTkFont(family="Segoe UI", size=13, weight="bold"),
        )
        self.lbl_url.grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))

        # Entry + Paste button row
        self.url_input_box = customtkinter.CTkFrame(self.url_frame, fg_color="transparent")
        self.url_input_box.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))
        self.url_input_box.grid_columnconfigure(0, weight=1)

        self.url_entry = customtkinter.CTkEntry(
            self.url_input_box,
            placeholder_text=self._t("url_placeholder"),
            height=38,
            corner_radius=8,
            font=customtkinter.CTkFont(family="Segoe UI", size=12),
        )
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.url_entry.bind("<KeyRelease>", self._on_url_change)

        self.btn_paste = customtkinter.CTkButton(
            self.url_input_box,
            text=self._t("btn_paste"),
            width=90,
            height=38,
            corner_radius=8,
            font=customtkinter.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._on_paste,
        )
        self.btn_paste.grid(row=0, column=1, sticky="e")

        # Detection badges row
        self.badges_box = customtkinter.CTkFrame(self.url_frame, fg_color="transparent")
        self.badges_box.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 10))

        self.lbl_platform_title = customtkinter.CTkLabel(
            self.badges_box,
            text=self._t("platform_label"),
            font=customtkinter.CTkFont(family="Segoe UI", size=12),
            text_color=("gray40", "gray60"),
        )
        self.lbl_platform_title.pack(side="left", padx=(0, 6))

        self.badge_platform = customtkinter.CTkLabel(
            self.badges_box,
            text=" - ",
            fg_color="#6c757d",
            text_color="white",
            corner_radius=6,
            font=customtkinter.CTkFont(family="Segoe UI", size=11, weight="bold"),
            padx=10,
            pady=2,
        )
        self.badge_platform.pack(side="left", padx=(0, 14))

        self.lbl_content_title = customtkinter.CTkLabel(
            self.badges_box,
            text=self._t("content_type_label"),
            font=customtkinter.CTkFont(family="Segoe UI", size=12),
            text_color=("gray40", "gray60"),
        )
        self.lbl_content_title.pack(side="left", padx=(0, 6))

        self.badge_content_type = customtkinter.CTkLabel(
            self.badges_box,
            text=" - ",
            fg_color=("gray85", "gray25"),
            corner_radius=6,
            font=customtkinter.CTkFont(family="Segoe UI", size=11, weight="bold"),
            padx=10,
            pady=2,
        )
        self.badge_content_type.pack(side="left")

        # ==============================================================
        # 5. Download Folder Frame
        # ==============================================================
        self.folder_frame = customtkinter.CTkFrame(self.main_container, corner_radius=10)
        self.folder_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self.folder_frame.grid_columnconfigure(0, weight=1)

        self.lbl_folder = customtkinter.CTkLabel(
            self.folder_frame,
            text=self._t("folder_label"),
            font=customtkinter.CTkFont(family="Segoe UI", size=13, weight="bold"),
        )
        self.lbl_folder.grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))

        self.folder_box = customtkinter.CTkFrame(self.folder_frame, fg_color="transparent")
        self.folder_box.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        self.folder_box.grid_columnconfigure(0, weight=1)

        self.folder_entry = customtkinter.CTkEntry(
            self.folder_box,
            height=38,
            corner_radius=8,
            font=customtkinter.CTkFont(family="Segoe UI", size=12),
        )
        self.folder_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.folder_entry.insert(0, self.download_dir)

        self.btn_browse = customtkinter.CTkButton(
            self.folder_box,
            text=self._t("btn_browse"),
            width=90,
            height=38,
            corner_radius=8,
            font=customtkinter.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._on_browse,
        )
        self.btn_browse.grid(row=0, column=1, sticky="e")

        # ==============================================================
        # 6. Action Buttons Frame
        # ==============================================================
        self.action_frame = customtkinter.CTkFrame(self.main_container, fg_color="transparent")
        self.action_frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        self.action_frame.grid_columnconfigure(0, weight=1)

        self.btn_download = customtkinter.CTkButton(
            self.action_frame,
            text=self._t("btn_download"),
            height=45,
            corner_radius=10,
            fg_color="#28a745",
            hover_color="#218838",
            text_color="white",
            font=customtkinter.CTkFont(family="Segoe UI", size=14, weight="bold"),
            command=self._on_download,
        )
        self.btn_download.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.btn_cancel = customtkinter.CTkButton(
            self.action_frame,
            text=self._t("btn_cancel"),
            width=115,
            height=45,
            corner_radius=10,
            fg_color="#dc3545",
            hover_color="#c82333",
            text_color="white",
            font=customtkinter.CTkFont(family="Segoe UI", size=13, weight="bold"),
            state="disabled",
            command=self._on_cancel,
        )
        self.btn_cancel.grid(row=0, column=1, sticky="e", padx=(0, 8))

        self.btn_open_folder = customtkinter.CTkButton(
            self.action_frame,
            text=self._t("btn_open_folder"),
            width=125,
            height=45,
            corner_radius=10,
            fg_color=("#495057", "#343a40"),
            hover_color=("#343a40", "#212529"),
            text_color="white",
            font=customtkinter.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self._on_open_folder,
        )
        self.btn_open_folder.grid(row=0, column=2, sticky="e")

        # ==============================================================
        # 7. Progress Frame
        # ==============================================================
        self.progress_frame = customtkinter.CTkFrame(self.main_container, corner_radius=10)
        self.progress_frame.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        self.progress_frame.grid_columnconfigure(0, weight=1)

        # Status and percentage header
        self.progress_header = customtkinter.CTkFrame(self.progress_frame, fg_color="transparent")
        self.progress_header.grid(row=0, column=0, sticky="ew", padx=14, pady=(8, 4))
        self.progress_header.grid_columnconfigure(0, weight=1)

        self.status_box = customtkinter.CTkFrame(self.progress_header, fg_color="transparent")
        self.status_box.grid(row=0, column=0, sticky="w")

        self.lbl_status_title = customtkinter.CTkLabel(
            self.status_box,
            text=f"{self._t('progress_label')}:",
            font=customtkinter.CTkFont(family="Segoe UI", size=12, weight="bold"),
        )
        self.lbl_status_title.pack(side="left", padx=(0, 6))

        self.lbl_status_val = customtkinter.CTkLabel(
            self.status_box,
            text=self._t("status_ready"),
            font=customtkinter.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=("#28a745", "#2ecc71"),
        )
        self.lbl_status_val.pack(side="left")

        self.lbl_percentage_val = customtkinter.CTkLabel(
            self.progress_header,
            text="%0.0" if self.current_lang == "tr" else "0.0%",
            font=customtkinter.CTkFont(family="Segoe UI", size=13, weight="bold"),
        )
        self.lbl_percentage_val.grid(row=0, column=1, sticky="e")

        # Progress bar
        self.progress_bar = customtkinter.CTkProgressBar(
            self.progress_frame,
            height=12,
            corner_radius=6,
        )
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 6))
        self.progress_bar.set(0.0)

        # Metric labels row
        self.metrics_box = customtkinter.CTkFrame(self.progress_frame, fg_color="transparent")
        self.metrics_box.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 8))
        self.metrics_box.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.lbl_speed_val = customtkinter.CTkLabel(
            self.metrics_box,
            text=f"{self._t('speed')}: -",
            font=customtkinter.CTkFont(family="Segoe UI", size=11),
            text_color=("gray30", "gray70"),
        )
        self.lbl_speed_val.grid(row=0, column=0, sticky="w")

        self.lbl_eta_val = customtkinter.CTkLabel(
            self.metrics_box,
            text=f"{self._t('eta')}: -",
            font=customtkinter.CTkFont(family="Segoe UI", size=11),
            text_color=("gray30", "gray70"),
        )
        self.lbl_eta_val.grid(row=0, column=1, sticky="w")

        self.lbl_res_metric_val = customtkinter.CTkLabel(
            self.metrics_box,
            text=f"{self._t('resolution')}: {self.selected_resolution_key}",
            font=customtkinter.CTkFont(family="Segoe UI", size=11),
            text_color=("gray30", "gray70"),
        )
        self.lbl_res_metric_val.grid(row=0, column=2, sticky="w")

        self.lbl_engine_val = customtkinter.CTkLabel(
            self.metrics_box,
            text=f"{self._t('engine')}: -",
            font=customtkinter.CTkFont(family="Segoe UI", size=11),
            text_color=("gray30", "gray70"),
        )
        self.lbl_engine_val.grid(row=0, column=3, sticky="e")

        # ==============================================================
        # 8. Log Panel Frame
        # ==============================================================
        self.log_frame = customtkinter.CTkFrame(self.main_container, corner_radius=10)
        self.log_frame.grid(row=6, column=0, sticky="nsew")
        self.log_frame.grid_columnconfigure(0, weight=1)
        self.log_frame.grid_rowconfigure(1, weight=1)

        self.log_header = customtkinter.CTkFrame(self.log_frame, fg_color="transparent")
        self.log_header.grid(row=0, column=0, sticky="ew", padx=14, pady=(8, 4))
        self.log_header.grid_columnconfigure(0, weight=1)

        self.lbl_log_title = customtkinter.CTkLabel(
            self.log_header,
            text=self._t("log_title"),
            font=customtkinter.CTkFont(family="Segoe UI", size=12, weight="bold"),
        )
        self.lbl_log_title.grid(row=0, column=0, sticky="w")

        self.btn_clear_log = customtkinter.CTkButton(
            self.log_header,
            text=self._t("btn_clear_log"),
            width=70,
            height=24,
            corner_radius=6,
            font=customtkinter.CTkFont(family="Segoe UI", size=11),
            command=self._clear_log,
        )
        self.btn_clear_log.grid(row=0, column=1, sticky="e")

        self.log_textbox = customtkinter.CTkTextbox(
            self.log_frame,
            font=customtkinter.CTkFont(family="Consolas", size=11),
            wrap="word",
            corner_radius=8,
        )
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 10))
        self.log_textbox.configure(state="disabled")

        # Initial welcome log entry
        self._apply_log(f"System initialized. Ready for downloads.")

    # ==================================================================
    # Event Handlers & Callbacks
    # ==================================================================

    def _on_url_change(self, event=None):
        """Detect platform from URL entry and update badges."""
        url = self.url_entry.get().strip()
        if not url:
            self.badge_platform.configure(text=" - ", fg_color="#6c757d", text_color="white")
            self.badge_content_type.configure(text=" - ")
            return

        detection = None
        if URLDetector is not None:
            try:
                detection = URLDetector.detect(url)
            except Exception:
                detection = None

        if detection is None:
            detection = FallbackURLDetector.detect(url)

        platform = (detection.get("platform") or "").lower()
        content_type = (detection.get("content_type") or "").strip()

        # Color coding:
        # YouTube: red (#FF0000)
        # Instagram: gradient-like purple (#E1306C)
        # Twitter/X: blue (#1DA1F2)
        # TikTok: dark (#010101)
        # Unknown: gray (#6c757d)
        if "youtube" in platform:
            self.badge_platform.configure(text=" YouTube ", fg_color="#FF0000", text_color="white")
        elif "instagram" in platform:
            self.badge_platform.configure(text=" Instagram ", fg_color="#E1306C", text_color="white")
        elif "twitter" in platform or platform == "x":
            self.badge_platform.configure(text=" Twitter / X ", fg_color="#1DA1F2", text_color="white")
        elif "tiktok" in platform:
            self.badge_platform.configure(text=" TikTok ", fg_color="#010101", text_color="white")
        else:
            if platform:
                self.badge_platform.configure(text=f" {platform.capitalize()} ", fg_color="#6c757d", text_color="white")
            else:
                self.badge_platform.configure(text=f" {self._t('platform_unknown')} ", fg_color="#6c757d", text_color="white")

        self.badge_content_type.configure(text=f" {content_type.capitalize()} " if content_type else " - ")

    def _on_paste(self):
        """Paste URL from clipboard and trigger auto-detection."""
        try:
            clipboard_content = self.clipboard_get()
            if clipboard_content:
                clean_url = clipboard_content.strip()
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, clean_url)
                self._on_url_change()
                self._append_log(f"Clipboard pasted: {clean_url[:65]}{'...' if len(clean_url) > 65 else ''}")
        except Exception as e:
            self._append_log(f"Clipboard read error: {e}")

    def _on_format_change(self, value: str):
        """Enable or disable resolution dropdown based on format selection."""
        if value == self.audio_display_str:
            self.selected_format = "audio"
            self.resolution_menu.configure(state="disabled")
            self.lbl_resolution.configure(text_color="gray")
        else:
            self.selected_format = "video"
            self.resolution_menu.configure(state="normal")
            self.lbl_resolution.configure(text_color=("gray10", "gray90"))

        try:
            self.config.set("format", self.selected_format)
            self.config.save()
        except Exception:
            pass

    def _on_resolution_change(self, value: str):
        """Store selected resolution key and save to config."""
        res_key = self.display_to_res_key.get(value, "1080p")
        self.selected_resolution_key = res_key
        self.lbl_res_metric_val.configure(text=f"{self._t('resolution')}: {res_key}")

        try:
            self.config.set("resolution", res_key)
            self.config.save()
        except Exception:
            pass

    def _on_language_change(self, value: str):
        """Switch language, refresh UI texts, and persist to config."""
        lang_code = LANG_CODE_MAP.get(value, "tr")
        if lang_code != self.current_lang:
            self.current_lang = lang_code
            try:
                self.config.set("language", lang_code)
                self.config.save()
            except Exception:
                pass
            self._refresh_ui_texts()
            self._append_log(f"Language changed to: {value}")

    def _on_theme_change(self, value: str):
        """Switch application appearance theme and persist to config."""
        theme_key = self.display_to_theme.get(value, "system")
        self.current_theme = theme_key
        customtkinter.set_appearance_mode(theme_key)
        try:
            self.config.set("theme", theme_key)
            self.config.save()
        except Exception:
            pass
        self._append_log(f"Theme changed to: {value}")

    def _on_browse(self):
        """Open folder browser dialog and update download directory."""
        current_dir = self.folder_entry.get().strip()
        if not current_dir or not os.path.exists(current_dir):
            current_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            if not os.path.exists(current_dir):
                current_dir = os.path.expanduser("~")

        chosen_dir = filedialog.askdirectory(
            title=self._t("folder_label"),
            initialdir=current_dir,
        )
        if chosen_dir:
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, chosen_dir)
            self.download_dir = chosen_dir
            try:
                self.config.set("download_dir", chosen_dir)
                self.config.save()
            except Exception:
                pass
            self._append_log(f"Download directory set to: {chosen_dir}")

    def _on_download(self):
        """Validate inputs and launch download via DownloaderEngine."""
        url = self.url_entry.get().strip()
        if not url:
            msg = self._t("err_invalid_url")
            self._append_log(f"Warning: {msg}")
            try:
                messagebox.showwarning(self._t("app_title"), msg)
            except Exception:
                pass
            return

        output_dir = self.folder_entry.get().strip()
        if not output_dir:
            output_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, output_dir)

        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            self._append_log(f"Failed to create directory {output_dir}: {e}")
            return

        if self.engine is None:
            self._append_log("Error: DownloaderEngine is not initialized.")
            return

        if self.engine.is_downloading():
            self._append_log("Warning: A download is already in progress.")
            return

        # Disable interactive inputs during download
        self.btn_download.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.url_entry.configure(state="disabled")
        self.btn_paste.configure(state="disabled")
        self.format_segmented_btn.configure(state="disabled")
        self.resolution_menu.configure(state="disabled")
        self.folder_entry.configure(state="disabled")
        self.btn_browse.configure(state="disabled")

        # Reset progress elements
        self.progress_bar.set(0.0)
        pct_zero = "%0.0" if self.current_lang == "tr" else "0.0%"
        self.lbl_percentage_val.configure(text=pct_zero)
        self.lbl_speed_val.configure(text=f"{self._t('speed')}: -")
        self.lbl_eta_val.configure(text=f"{self._t('eta')}: -")
        self.lbl_res_metric_val.configure(text=f"{self._t('resolution')}: {self.selected_resolution_key}")
        self._apply_status("downloading")

        self._append_log(self._t("download_started", url=url))
        self._append_log(f"Mode: {self.selected_format.upper()} | Target Resolution: {self.selected_resolution_key}")

        # Start download in engine
        try:
            self.engine.download(
                url=url,
                output_dir=output_dir,
                resolution_key=self.selected_resolution_key,
                mode=self.selected_format,
                progress_callback=self._update_progress,
                log_callback=self._append_log,
                status_callback=self._on_status_change,
                completion_callback=self._on_download_complete,
            )
        except Exception as e:
            self._append_log(f"Download start failure: {e}")
            self._on_download_complete(False, str(e))

    def _on_cancel(self):
        """Cancel ongoing download."""
        if self.engine and self.engine.is_downloading():
            self._append_log(self._t("status_cancelled"))
            try:
                self.engine.cancel()
            except Exception as e:
                self._append_log(f"Cancel error: {e}")
            self.btn_cancel.configure(state="disabled")

    def _on_open_folder(self):
        """Open download folder in OS file manager."""
        folder = self.folder_entry.get().strip()
        if not folder or not os.path.exists(folder):
            folder = os.path.join(os.path.expanduser("~"), "Downloads")
            if not os.path.exists(folder):
                folder = os.path.expanduser("~")

        try:
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
            self._append_log(f"Opened folder: {folder}")
        except Exception as e:
            self._append_log(f"Could not open directory {folder}: {e}")

    # ==================================================================
    # Thread-Safe UI Update Routines
    # ==================================================================

    def _update_progress(self, data: dict):
        """Thread-safe progress dispatch."""
        self.after(0, self._apply_progress, data)

    def _apply_progress(self, data: dict):
        """Update progress metrics on GUI thread."""
        try:
            percentage = float(data.get("percentage", 0.0))
            speed = str(data.get("speed", "-"))
            eta = str(data.get("eta", "-"))
            engine_name = str(data.get("engine", ""))
            resolution = str(data.get("resolution", self.selected_resolution_key))

            self.current_speed = speed
            self.current_eta = eta
            if engine_name:
                self.current_engine = engine_name

            norm = max(0.0, min(1.0, percentage / 100.0))
            self.progress_bar.set(norm)

            pct_text = f"%{percentage:.1f}" if self.current_lang == "tr" else f"{percentage:.1f}%"
            self.lbl_percentage_val.configure(text=pct_text)
            self.lbl_speed_val.configure(text=f"{self._t('speed')}: {speed}")
            self.lbl_eta_val.configure(text=f"{self._t('eta')}: {eta}")
            self.lbl_res_metric_val.configure(text=f"{self._t('resolution')}: {resolution}")
            if self.current_engine != "-":
                self.lbl_engine_val.configure(text=f"{self._t('engine')}: {self.current_engine}")
        except Exception:
            pass

    def _append_log(self, message: str):
        """Thread-safe log dispatch."""
        self.after(0, self._apply_log, message)

    def _apply_log(self, message: str):
        """Append message to log textbox on GUI thread."""
        try:
            self.log_textbox.configure(state="normal")
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            self.log_textbox.insert("end", f"[{timestamp}] {message}\n")
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")
        except Exception:
            pass

    def _clear_log(self):
        """Clear all messages from the log textbox."""
        try:
            self.log_textbox.configure(state="normal")
            self.log_textbox.delete("1.0", "end")
            self.log_textbox.configure(state="disabled")
        except Exception:
            pass

    def _on_status_change(self, status: str):
        """Thread-safe status dispatch."""
        self.after(0, self._apply_status, status)

    def _apply_status(self, status: str):
        """Update status indicators and button states."""
        try:
            st = (status or "").lower()
            if "downloading" in st:
                txt = self._t("status_downloading")
                color = ("#1f77b4", "#3a96d8")
                self.btn_download.configure(state="disabled")
                self.btn_cancel.configure(state="normal")
            elif "complete" in st:
                txt = self._t("status_completed")
                color = ("#28a745", "#2ecc71")
                self.btn_download.configure(state="normal")
                self.btn_cancel.configure(state="disabled")
            elif "cancel" in st:
                txt = self._t("status_cancelled")
                color = ("#dc3545", "#e74c3c")
                self.btn_download.configure(state="normal")
                self.btn_cancel.configure(state="disabled")
            elif "fail" in st or "error" in st:
                txt = self._t("status_failed")
                color = ("#dc3545", "#e74c3c")
                self.btn_download.configure(state="normal")
                self.btn_cancel.configure(state="disabled")
            else:
                txt = status.capitalize()
                color = ("gray20", "gray80")

            self.lbl_status_val.configure(text=txt, text_color=color)
        except Exception:
            pass

    def _on_download_complete(self, success: bool, result: str):
        """Thread-safe download completion dispatch."""
        self.after(0, self._apply_download_complete, success, result)

    def _apply_download_complete(self, success: bool, result: str):
        """Re-enable UI elements and present download outcome."""
        try:
            # Re-enable interactive widgets
            self.btn_download.configure(state="normal")
            self.btn_cancel.configure(state="disabled")
            self.url_entry.configure(state="normal")
            self.btn_paste.configure(state="normal")
            self.format_segmented_btn.configure(state="normal")
            if self.selected_format == "video":
                self.resolution_menu.configure(state="normal")
            self.folder_entry.configure(state="normal")
            self.btn_browse.configure(state="normal")

            if success:
                self.progress_bar.set(1.0)
                pct_full = "%100.0" if self.current_lang == "tr" else "100.0%"
                self.lbl_percentage_val.configure(text=pct_full)
                status_txt = self._t("status_completed")
                self.lbl_status_val.configure(text=status_txt, text_color=("#28a745", "#2ecc71"))
                self._apply_log(f"SUCCESS: {self._t('download_finished', path=result)}")
            else:
                status_txt = self._t("status_failed")
                self.lbl_status_val.configure(text=status_txt, text_color=("#dc3545", "#e74c3c"))
                self._apply_log(f"FAILURE: {result}")
        except Exception as e:
            self._apply_log(f"Error updating completion state: {e}")

    # ==================================================================
    # Dynamic Language & Text Refresh
    # ==================================================================

    def _refresh_ui_texts(self):
        """Update all UI widget texts to match current language."""
        # Window & Header
        self.title(self._t("app_title"))
        self.lbl_title.configure(text=self._t("app_title"))
        self.lbl_subtitle.configure(text=self._t("app_subtitle"))

        # Language dropdown
        current_lang_name = LANG_NAME_MAP.get(self.current_lang, "Türkçe")
        self.lang_menu.set(current_lang_name)

        # Theme dropdown
        self.display_to_theme = {}
        self.theme_to_display = {}
        theme_displays = []
        for trans_key, theme_key in THEME_MAPPING:
            disp = self._t(trans_key)
            self.display_to_theme[disp] = theme_key
            self.theme_to_display[theme_key] = disp
            theme_displays.append(disp)

        self.theme_menu.configure(values=theme_displays)
        self.theme_menu.set(self.theme_to_display.get(self.current_theme, theme_displays[0]))

        # Format & Resolution labels
        self.lbl_format.configure(text=self._t("format"))
        self.lbl_resolution.configure(text=self._t("resolution"))

        self.video_display_str = self._t("format_video")
        self.audio_display_str = self._t("format_audio")
        self.format_segmented_btn.configure(values=[self.video_display_str, self.audio_display_str])
        self.format_segmented_btn.set(
            self.audio_display_str if self.selected_format == "audio" else self.video_display_str
        )

        # Resolution dropdown options
        self.display_to_res_key = {}
        self.res_key_to_display = {}
        res_displays = []
        for trans_key, res_key in RESOLUTION_MAPPING:
            disp = self._t(trans_key)
            self.display_to_res_key[disp] = res_key
            self.res_key_to_display[res_key] = disp
            res_displays.append(disp)

        self.resolution_menu.configure(values=res_displays)
        active_res_disp = self.res_key_to_display.get(self.selected_resolution_key, res_displays[0])
        self.resolution_menu.set(active_res_disp)

        # If audio is selected, ensure resolution menu is disabled
        if self.selected_format == "audio":
            self.resolution_menu.configure(state="disabled")
            self.lbl_resolution.configure(text_color="gray")
        else:
            self.resolution_menu.configure(state="normal")
            self.lbl_resolution.configure(text_color=("gray10", "gray90"))

        # URL Input & Badges
        self.lbl_url.configure(text=self._t("url_label"))
        self.url_entry.configure(placeholder_text=self._t("url_placeholder"))
        self.btn_paste.configure(text=self._t("btn_paste"))
        self.lbl_platform_title.configure(text=self._t("platform_label"))
        self.lbl_content_title.configure(text=self._t("content_type_label"))
        self._on_url_change()

        # Download Folder
        self.lbl_folder.configure(text=self._t("folder_label"))
        self.btn_browse.configure(text=self._t("btn_browse"))

        # Action Buttons
        self.btn_download.configure(text=self._t("btn_download"))
        self.btn_cancel.configure(text=self._t("btn_cancel"))
        self.btn_open_folder.configure(text=self._t("btn_open_folder"))

        # Progress Frame
        self.lbl_status_title.configure(text=f"{self._t('progress_label')}:")
        if not (self.engine and self.engine.is_downloading()):
            self.lbl_status_val.configure(text=self._t("status_ready"))

        self.lbl_speed_val.configure(text=f"{self._t('speed')}: {self.current_speed}")
        self.lbl_eta_val.configure(text=f"{self._t('eta')}: {self.current_eta}")
        self.lbl_res_metric_val.configure(text=f"{self._t('resolution')}: {self.selected_resolution_key}")
        self.lbl_engine_val.configure(text=f"{self._t('engine')}: {self.current_engine}")

        # Log Panel
        self.lbl_log_title.configure(text=self._t("log_title"))
        self.btn_clear_log.configure(text=self._t("btn_clear_log"))

    # ==================================================================
    # Window Lifecycle & Teardown
    # ==================================================================

    def _on_closing(self):
        """Save settings to configuration and terminate cleanly."""
        try:
            self.config.set("window_geometry", self.geometry())
            self.config.set("download_dir", self.folder_entry.get().strip())
            self.config.set("resolution", self.selected_resolution_key)
            self.config.set("format", self.selected_format)
            self.config.set("language", self.current_lang)
            self.config.set("theme", self.current_theme)
            self.config.save()
        except Exception as e:
            print(f"Error saving config on shutdown: {e}")

        try:
            if self.engine and self.engine.is_downloading():
                self.engine.cancel()
        except Exception:
            pass

        self.destroy()
