# Contributing

Run `python3 -m unittest discover -s tests -v`. The tests do not access a real
microphone or type into your desktop.

The GUI smoke test **must** use an isolated display:

```bash
VOICE_ISLAND_ISOLATED_TEST=1 xvfb-run -a python3 tests/gui_smoke.py
```

It uses synthetic audio, a loopback-only HTTP fixture and a test editor. Install
GTK/Cairo, NumPy, Requests, Xvfb, Xauth and xdotool first. For stricter isolation,
run inside a private network/device namespace or a disposable test container.

Preserve focus checks, cancellation, recording bounds and the absence of
transcript logging. Do not add automatic provider fallback or telemetry.
Reports should include the desktop/session type, backend API contract, steps
to reproduce and actual versus expected behavior. Remove recordings, tokens
and personal endpoints before sharing logs.

Accessibility work should describe a concrete user workflow and separate
implemented behavior from proposed improvements. Feedback from users with
different interaction needs is welcome.
