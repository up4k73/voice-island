# Validation scope

The original Linux tool is used by its author in everyday work. The standalone
package preserves its overlay drawing and ordinary toggle-dictation workflow,
while removing personal integrations and machine-specific configuration.

Automated tests cover:

- configuration validation and non-overwriting example creation;
- mono PCM16/WAV encoding and FFT display scaling;
- explicit HTTP endpoints, long-audio routing and malformed/error responses;
- no automatic upload retries;
- ignored late results after cancellation;
- no automatic typing after a window-focus change;
- transcript delivery through stdin, rather than process arguments;
- clipboard output without invoking keyboard tools;
- private local shortcut commands and single-instance ownership.

The GUI check runs on an isolated X11 display with a synthetic audio subprocess,
a local HTTP fixture and a dedicated text editor. It exercises the actual
capture reader, WAV upload, GTK overlay and `xdotool` insertion of mixed
Cyrillic/Latin text. No real microphone, user documents or external recognition
service are involved in that test.

This validates the packaged client path, not speech-model accuracy. Live
recognition quality, atypical speech, native Wayland, assistive devices and
screen-reader workflows remain separate validation tasks.
