import os
import requests
from pathlib import Path

def download_file(url, filename):
    response = requests.get(url)
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded {filename}")
    else:
        print(f"Failed to download {filename}")

def main():
    # Create sounds directory if it doesn't exist
    sounds_dir = Path("static/sounds")
    sounds_dir.mkdir(parents=True, exist_ok=True)

    # Sound effect URLs (using free, royalty-free sounds)
    sounds = {
        "hover.mp3": "https://assets.mixkit.co/active_storage/sfx/2568/2568-preview.mp3",
        "correct.mp3": "https://assets.mixkit.co/active_storage/sfx/1434/1434-preview.mp3",
        "wrong.mp3": "https://assets.mixkit.co/active_storage/sfx/2570/2570-preview.mp3",
        "timeout.mp3": "https://assets.mixkit.co/active_storage/sfx/124/124-preview.mp3",
        "ambient.mp3": "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3?filename=lofi-study-112191.mp3"  # Lo-fi study music from Pixabay
    }

    # Download each sound file
    for filename, url in sounds.items():
        filepath = sounds_dir / filename
        if not filepath.exists():
            download_file(url, filepath)

if __name__ == "__main__":
    main() 