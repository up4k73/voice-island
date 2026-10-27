# Voice Island

**Speak, toggle, keep writing.** A Linux dictation client with a compact,
Dynamic Island-style recording indicator.

[Русский](README.ru.md) · [Installation](docs/INSTALL.md) · [Speech backend](docs/BACKEND.md) · [Accessibility roadmap](ROADMAP.md)

![Voice Island preview with synthetic audio](docs/images/preview.png)

Voice Island grew out of a tool its author uses in everyday work. A shortcut
starts recording; pressing it again sends the audio to your chosen speech
recognition service and inserts the transcript into the focused application.
The small overlay shows recording, processing and result states, then hides.

## Features

- Toggle recording without holding a key down.
- Animated spectrum with **five themes** and **four bar styles**.
- Global shortcuts through your desktop's shortcut settings.
- Optional direct keyboard-device binding.
- Configurable HTTP speech backend; no built-in cloud account or hidden fallback.
- Unicode-safe clipboard paste or manual clipboard output. If window focus changes during recognition,
  the result is copied instead of being typed into a different window.
- Cancellation and a configurable recording-length limit.

The desktop client supports **Linux on X11**, GTK 3 and PulseAudio-compatible
capture, including PipeWire's PulseAudio service. Native Wayland typing is not
implemented. A compatible speech recognition backend is required; model weights
are not bundled. The preview image uses synthetic audio and is labeled DEMO.

## Quick start

On Debian/Ubuntu, install the desktop dependencies:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-numpy python3-requests pulseaudio-utils xdotool
git clone https://github.com/up4k73/voice-island.git
cd voice-island
./bin/voice-island --preview
```

For real dictation, configure your [speech backend](docs/BACKEND.md), then run:

```bash
./bin/voice-island --url http://127.0.0.1:9875/transcribe
```

In your desktop's global shortcut settings, bind a key such as Pause to:

```bash
/absolute/path/to/voice-island/bin/voice-island --toggle
```

Use `--cancel` to discard a recording or ignore a pending result, and `--quit`
to stop the application. `--toggle` also starts the application if it is not
already running. The active instance owns the configuration; a shortcut does
not change it.

## Appearance

Themes: `matrix`, `fire`, `electric`, `plasma`, `ice`.

Styles: `solid`, `blocks`, `bounce`, `dots`.

```bash
./bin/voice-island --preview --theme ice --style dots
./bin/voice-island --init-config
```

Edit `~/.config/voice-island/config.json` to keep your preferences. Quit and
restart the app after changing its configuration. See [installation](docs/INSTALL.md).

## Accessibility direction

The current toggle interaction reduces the need to hold a key while speaking.
Future work focuses on alternative input switches, opt-in voice commands,
audible status feedback, more adjustable visuals and easier setup.

These are development plans, not a claim of accessibility certification or
completed testing with disabled users. See the [roadmap](ROADMAP.md) for the
boundary between current behavior and planned work.

## Privacy and validation

Audio is held in memory and sent only to the endpoint you configure. The client
does not save recordings or log recognized text. Your speech service and your
desktop clipboard manager have their own data-handling behavior.

Default insertion updates the clipboard and sends Ctrl+V. For a terminal, set
the paste shortcut to Ctrl+Shift+V. A legacy simulated-typing mode is also
available, but character support depends on the keyboard map.

Tests cover audio encoding, HTTP failures, cancellation, focus changes and local
shortcut commands. An isolated GUI check exercises synthetic PCM → WAV upload →
response → actual text insertion into a test editor. See [validation](docs/VALIDATION.md).

```bash
python3 -m unittest discover -s tests -v
```

[MIT license](LICENSE). Dependencies and speech models retain their own licenses.
