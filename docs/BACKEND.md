# Speech recognition backend

Voice Island is a desktop client. Recognition runs in a service you configure,
on the same computer or on your own server. No model weights, private service
addresses or provider account are included.

## API contract

The client sends one request per completed recording:

```http
POST /transcribe
Content-Type: multipart/form-data; boundary=...

file: audio.wav (audio/wav)
language: ru
```

Audio is mono, 16 kHz, signed 16-bit little-endian PCM in a WAV container.
A successful response is HTTP 2xx with JSON:

```json
{"text": "Recognized speech"}
```

Additional JSON fields are ignored. An empty `text` means no speech was
recognized. Non-2xx responses and malformed JSON are errors. The client does
not follow redirects or retry the upload. Timeouts are 3 seconds to connect
and 120 seconds to read.

If `long_url` is configured, recordings longer than 25 seconds go there.
Otherwise they use `url`; set `max_seconds` to your backend's supported limit.
Optional bearer authentication reads `VOICE_ISLAND_TOKEN` from the environment.
Use HTTPS for an endpoint outside your trusted local setup.

## Optional local GigaAM example

`examples/gigaam_server.py` is a small local adapter for Russian dictation
using GigaAM `v3_e2e_rnnt`. It handles recordings up to **25 seconds**, validates
WAV input, serializes model calls and removes temporary audio after each call.

Install `ffmpeg` and follow the upstream [GigaAM installation requirements](https://github.com/salute-developers/GigaAM#setup).
Use a separate environment for the model dependencies:

```bash
python3 -m venv .asr-venv
.asr-venv/bin/pip install 'gigaam[torch] @ git+https://github.com/salute-developers/GigaAM.git'
.asr-venv/bin/python examples/gigaam_server.py
```

The model package downloads its weights on first use and can require substantial
memory/compute. Start the client in another terminal with the matching limit:

```bash
./bin/voice-island --url http://127.0.0.1:9875/transcribe --max-seconds 25
```

The example binds only to localhost by default and provides no authentication.
Its HTTP validation and cleanup are tested with a model substitute; downloading
and running the model is separate from the client's CI checks. Other languages
or longer recordings need a backend that supports them.

## Choosing another backend

The original daily-use setup used self-hosted services exposing this contract,
including a wrapper around [GigaAM](https://github.com/salute-developers/GigaAM).
GigaAM is a separate project; its model installation, hardware requirements and
license apply independently. Its normal `transcribe` method supports recordings
up to 25 seconds; longer input needs its long-form path or server-side chunking.

A model library by itself is not this HTTP API. Use the example above, a
compatible service, or adapt an existing one. Other servers may require extra
fields or return a different schema; do not assume every transcription API is
compatible. Supported languages and recognition accuracy depend on the backend.

The isolated GUI test includes a local fixture that returns a fixed sentence.
It validates transport and insertion only and must not be used as a speech
recognition service.
