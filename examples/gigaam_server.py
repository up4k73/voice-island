#!/usr/bin/env python3
"""Optional local GigaAM adapter for short dictation (up to 25 seconds)."""
import argparse
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import tempfile
import threading
import wave

MAX_REQUEST = 2 * 1024 * 1024


def transcribe_request(body, content_type, model):
    if len(body) > MAX_REQUEST or not content_type.startswith("multipart/form-data;"):
        raise ValueError("Expected a bounded multipart upload")
    if "\r" in content_type or "\n" in content_type:
        raise ValueError("Invalid content type")
    message = BytesParser(policy=policy.default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body)
    files = [part for part in message.iter_parts()
             if part.get_param("name", header="Content-Disposition") == "file"]
    if len(files) != 1:
        raise ValueError("Expected one file field")
    audio = files[0].get_payload(decode=True)
    with wave.open(io.BytesIO(audio), "rb") as recording:
        if (recording.getnchannels(), recording.getsampwidth(), recording.getframerate(), recording.getcomptype()) != (1,2,16000,"NONE"):
            raise ValueError("Expected mono PCM16 WAV at 16 kHz")
        if not 0 < recording.getnframes() <= 25 * 16000:
            raise ValueError("This example supports recordings up to 25 seconds")
    with tempfile.TemporaryDirectory(prefix="voice-island-asr-") as directory:
        path = Path(directory) / "audio.wav"
        path.write_bytes(audio)
        result = model.transcribe(str(path))
    text = result if isinstance(result, str) else getattr(result, "text", None)
    if not isinstance(text, str):
        raise RuntimeError("Unsupported model response")
    return text.strip()


def serve(model, host="127.0.0.1", port=9875):
    lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, payload):
            data = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self.reply(200, {"status":"ready"}) if self.path == "/health" else self.reply(404,{"error":"Not found"})

        def do_POST(self):
            if self.path != "/transcribe":
                self.reply(404,{"error":"Not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_REQUEST:
                    self.reply(413,{"error":"Invalid upload size"})
                    return
                self.connection.settimeout(30)
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError("Incomplete upload")
                with lock:
                    text = transcribe_request(body,self.headers.get("Content-Type",""),model)
                self.reply(200,{"text":text})
            except (ValueError, wave.Error, EOFError):
                self.reply(400,{"error":"Expected mono 16 kHz PCM WAV, at most 25 seconds"})
            except Exception:
                self.reply(500,{"error":"Recognition failed"})

        def log_message(self, *args):
            pass

    print(f"Local speech adapter listening on {host}:{port}",flush=True)
    ThreadingHTTPServer((host,port),Handler).serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9875)
    parser.add_argument("--model", default="v3_e2e_rnnt")
    args = parser.parse_args()
    import gigaam
    model = gigaam.load_model(args.model)
    serve(model,args.host,args.port)
