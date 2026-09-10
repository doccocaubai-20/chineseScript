from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    from yt_dlp import YoutubeDL
except ImportError:
    print("Chưa cài yt-dlp. Chạy: python -m pip install yt-dlp")
    raise SystemExit(1)


def is_tiktok_url(value: str) -> bool:
    hostname = urlparse(value).hostname or ""
    hostname = hostname.lower().removeprefix("www.")
    return hostname in {"tiktok.com", "vm.tiktok.com", "vt.tiktok.com"} or hostname.endswith(".tiktok.com")


def main() -> int:
    source_url = sys.argv[1].strip() if len(sys.argv) > 1 else input("Dán link TikTok: ").strip()
    if not source_url or not is_tiktok_url(source_url):
        print("Link không hợp lệ. Hãy dùng link tiktok.com, vm.tiktok.com hoặc vt.tiktok.com.")
        return 1

    project_root = Path(__file__).resolve().parents[1]
    output_directory = project_root / "media" / "tiktok"
    output_directory.mkdir(parents=True, exist_ok=True)
    options = {
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "outtmpl": str(output_directory / "%(title).120s [%(id)s].%(ext)s"),
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 60,
    }

    print(f"Đang tải vào: {output_directory}")
    try:
        with YoutubeDL(options) as downloader:
            info = downloader.extract_info(source_url, download=True)
        print(f"\nĐã tải: {info.get('title', info.get('id', 'video'))}")
        print(f"Thư mục: {output_directory}")
        return 0
    except Exception as error:
        print(f"\nTải TikTok thất bại: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
