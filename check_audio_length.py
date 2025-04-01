from mutagen.mp3 import MP3

def get_audio_length(file_path):
    audio = MP3(file_path)
    length_in_seconds = audio.info.length
    minutes = int(length_in_seconds // 60)
    seconds = int(length_in_seconds % 60)
    return f"{minutes} minutes and {seconds} seconds"

if __name__ == "__main__":
    length = get_audio_length("static/sounds/ambient.mp3")
    print(f"Audio length: {length}") 