# Installation and use

## Desktop dependencies

Voice Island requires Python 3.10+, GTK 3/PyGObject with Cairo bindings,
NumPy, Requests, `parec` and `xdotool`. On Debian/Ubuntu:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-numpy python3-requests pulseaudio-utils xdotool
```

Run it from the checkout using `./bin/voice-island`. Keep the checkout in place
if a desktop shortcut points to it. Other distributions can use equivalent
packages. An optional Python installation into a virtual environment is also
supported; use `--system-site-packages` to expose the distribution's GTK bindings.

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install --upgrade pip setuptools wheel
.venv/bin/pip install .
.venv/bin/voice-island --preview
```

The client does not contain a recognition model. Set up a compatible
[backend](BACKEND.md) before expecting dictation to produce text.

## Persistent configuration

```bash
./bin/voice-island --init-config
```

The command creates `~/.config/voice-island/config.json`, or the equivalent
under `XDG_CONFIG_HOME`. It refuses to overwrite an existing file.

| Setting | Meaning |
| --- | --- |
| `url` | Speech endpoint; default `http://127.0.0.1:9875/transcribe` |
| `long_url` | Optional separate endpoint for recordings longer than 25 seconds |
| `language` | Language sent to the backend; default `ru` |
| `source` | PulseAudio/PipeWire source name; empty selects the current default |
| `theme` | `matrix`, `fire`, `electric`, `plasma`, `ice` |
| `style` | `solid`, `blocks`, `bounce`, `dots` |
| `output` | `paste` (default), `type` or `clipboard` |
| `paste_shortcut` | Default `ctrl+v`; use `ctrl+shift+v` for a terminal |
| `max_seconds` | Recording limit, 1–600 seconds; default 120 |
| `top_offset` | Overlay position below the primary monitor's top edge |
| `meter_floor_db` | Display sensitivity; this is a visual indicator, not a calibrated meter |

Command-line arguments override settings for a newly started instance. A
running instance keeps its own configuration. Change settings after quitting
and restart. Use `pactl list short sources` to inspect available microphones.

## Global shortcuts

Bind a key in your desktop's shortcut settings to the full path of
`bin/voice-island --toggle`. In KDE Plasma, use System Settings → Keyboard →
Shortcuts and add the command. This route does not require access to raw
keyboard devices. A first toggle starts the app and recording; the next stops
recording and transcribes. While processing, further toggles are ignored.

Bind a second shortcut to `--cancel` if desired. Cancellation ignores any late
recognition result. An HTTP request already sent to the service cannot be
recalled. Cancellation stops further typing, but does not undo text already inserted.
`--quit` stops the application and its active microphone process.

To start the listener at login, add the full-path command without `--toggle`
to your desktop's autostart settings. No autostart entry is installed
automatically.

## Optional direct keyboard binding

For setups without a desktop shortcut manager, install `python3-evdev` or the
Python `keyboard` extra and explicitly choose a keyboard device:

```bash
./bin/voice-island --device /dev/input/by-id/YOUR-KEYBOARD-event-kbd --key pause
```

Keys: `pause`, `scroll_lock`, `print_screen`, `f9`–`f12`, `insert`. Modifier
combinations and repeated key-down events are ignored. The selected device
must already be readable by your user. The app does not change input-device
permissions, grab the keyboard, or log keystrokes. Desktop-managed shortcuts
are recommended for ordinary installations.

## Output and focus

The default output copies the transcript to the clipboard and sends the
configured paste shortcut, avoiding Unicode key-mapping races. This replaces
the current clipboard contents. For a terminal, configure `ctrl+shift+v`.
Legacy `type` mode simulates individual keys and can be unreliable for
characters absent from the X11 keyboard map; prefer paste for multilingual text.

Dictation remembers the focused X11 window when recording starts. If that
window changes, the result is copied to the clipboard for manual insertion.
It does not track cursor movement or changed fields within the same window.
Use clipboard mode when automatic typing is unsuitable.

Transcript whitespace is folded into a single line to avoid sending Return
into forms. Paragraph editing and explicit voice commands are future work.
`xdotool` compatibility varies between applications; a failed insertion can
leave partial text, so inspect it before pasting the clipboard fallback.

## Troubleshooting

- No GTK/Cairo import: install the desktop dependencies for the Python interpreter
  actually running the app. Pip alone does not install system GTK libraries.
- No recording: check the default input/source and that `parec` is installed.
- Recognition fails: verify the configured backend and its supported audio
  duration. The client does not silently switch providers or retry uploads.
- Wayland session: use an X11 session for this release. Native Wayland input is
  planned, not currently supported.
- Overlay stays absent: run `--preview` from a terminal inside the graphical session.
- Clipboard fallback: keep the app running until you paste, especially without
  a clipboard manager.
