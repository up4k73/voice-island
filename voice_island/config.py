"""Portable settings; no machine-specific endpoints or credentials."""
from dataclasses import asdict, dataclass
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Config:
    url: str = "http://127.0.0.1:9875/transcribe"
    long_url: str = ""
    language: str = "ru"
    source: str = ""
    theme: str = "electric"
    style: str = "solid"
    output: str = "paste"
    paste_shortcut: str = "ctrl+v"
    max_seconds: int = 120
    top_offset: int = 8
    meter_floor_db: float = -60.0

    def validate(self):
        for url in [self.url] + ([self.long_url] if self.long_url else []):
            parsed = urlsplit(url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
                raise ValueError("Use an HTTP(S) transcription URL without embedded credentials")
        if self.theme not in {"matrix", "fire", "electric", "plasma", "ice"}:
            raise ValueError("Unknown theme")
        if self.style not in {"solid", "blocks", "bounce", "dots"}:
            raise ValueError("Unknown bar style")
        if self.output not in {"paste", "type", "clipboard"}:
            raise ValueError("Output must be paste, type or clipboard")
        if not isinstance(self.paste_shortcut,str) or not re.fullmatch(r"(?:[A-Za-z][A-Za-z0-9_]*\+)*[A-Za-z][A-Za-z0-9_]*",self.paste_shortcut):
            raise ValueError("Invalid paste shortcut")
        if not isinstance(self.max_seconds, int) or not 1 <= self.max_seconds <= 600:
            raise ValueError("max_seconds must be between 1 and 600")
        if not isinstance(self.top_offset, int) or not 0 <= self.top_offset <= 500:
            raise ValueError("top_offset must be between 0 and 500")
        if not isinstance(self.meter_floor_db, (int, float)) or not -100 <= self.meter_floor_db <= -10:
            raise ValueError("meter_floor_db must be between -100 and -10")
        if not isinstance(self.language, str) or len(self.language) > 32:
            raise ValueError("Invalid language code")
        if not isinstance(self.source, str):
            raise ValueError("Invalid audio source")
        return self


def config_path():
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "voice-island/config.json"


def load(path=None, overrides=None):
    path = Path(path) if path else config_path()
    values = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(values, dict):
        raise ValueError("Configuration must be a JSON object")
    values.update({k: v for k, v in (overrides or {}).items() if v is not None})
    return Config(**values).validate()


def write_example(path=None):
    path = Path(path) if path else config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(asdict(Config()), stream, indent=2)
        stream.write("\n")
    return path
