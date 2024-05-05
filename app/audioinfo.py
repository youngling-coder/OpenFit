import os.path
from typing import Union

import mutagen
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3


def __to_metadata(filepath: str):
    metadata = {}
    try:
        audio = MP3(filepath, ID3=EasyID3)

        # Extract metadata
        title = audio.get("title", [None])[0]
        artist = audio.get("artist", [None])[0]
        album = audio.get("album", [None])[0]
        duration = audio.info.length

        metadata = {
            "title": title,
            "artist": artist,
            "album": album,
            "duration_seconds": duration
        }
    except mutagen.MutagenError:
        pass
    finally:
        return metadata


def get_audio_name(audiopath: str) -> Union[dict, str]:

    metadata = __to_metadata(audiopath)
    if not (metadata['title'] and metadata['artist']):
        name = os.path.basename(audiopath)
    else:
        name = f"{metadata['title']} - {metadata['artist']}"

    return name
