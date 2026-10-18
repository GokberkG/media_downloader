import sys
import os
import subprocess


def hide_console():
    """Windows'ta py.exe veya python.exe ile açılan konsol penceresini gizler."""
    if sys.platform == "win32":
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass


def ensure_base_dependencies():
    """Ensure customtkinter and base packages are installed."""
    required = {
        "customtkinter": "customtkinter",
        "PIL": "Pillow",
        "packaging": "packaging",
    }
    for import_name, pip_name in required.items():
        try:
            __import__(import_name)
        except ImportError:
            print(f"Installing {pip_name}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name, "-q"])


def main():
    hide_console()
    ensure_base_dependencies()
    
    # Add project root to path
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from ui.app_window import MediaDownloaderApp
    
    app = MediaDownloaderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
