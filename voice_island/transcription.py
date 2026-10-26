"""One explicit transcription endpoint, no background upload or fallback."""
import os

import requests

from .audio import RATE, wave_bytes


def transcribe(pcm, config, post=requests.post):
    duration = len(pcm) / (RATE * 2)
    url = config.long_url if duration > 25 and config.long_url else config.url
    headers = {}
    token = os.environ.get("VOICE_ISLAND_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    response = post(url, files={"file": ("audio.wav", wave_bytes(pcm), "audio/wav")},
                    data={"language": config.language}, headers=headers,
                    timeout=(3, 120), allow_redirects=False)
    try:
        if not 200 <= response.status_code < 300:
            raise RuntimeError(f"Speech service returned HTTP {response.status_code}")
        result = response.json()
        if not isinstance(result, dict) or not isinstance(result.get("text"), str):
            raise ValueError("Speech service returned an invalid transcript")
        # Dictation inserts one text line; embedded newlines must not submit forms.
        return " ".join(result["text"].split())
    finally:
        response.close()
