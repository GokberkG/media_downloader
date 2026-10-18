"""Windows GUI launcher for Media Downloader (runs without console window)."""
import os
import sys

# Add project root to sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from main import main

if __name__ == "__main__":
    main()
