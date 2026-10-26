# Accessibility roadmap

Voice Island is intended to reduce friction in everyday computer use.
Its predecessor has been used privately in the author's daily workflow;
the standalone public package starts from that practical experience.

## Available today

- Toggle recording without holding a button.
- A compact indicator that hides when idle.
- Choice of visual theme and animation style.
- Desktop shortcut control and optional explicit keyboard-device binding.
- Clipboard output, cancellation and a changed-focus guard.
- User-selected speech backend without a mandatory cloud account.

These features have not been evaluated as an accessibility solution with a
representative group of disabled users. No accessibility certification or
recognition accuracy for atypical speech is claimed.

## Planned work

1. **Alternative activation:** configurable physical switches, foot pedals and
   controller buttons, with one-button workflows and clear cancellation.
2. **Opt-in voice commands:** start/stop recording, cancel, punctuation and
   deliberate text-editing actions. Separate commands from ordinary dictation
   and prevent accidental submission or destructive editing.
3. **Status feedback:** optional sounds and spoken recording/error states;
   investigate useful screen-reader announcements without stealing focus.
4. **Visual adjustments:** overlay size and placement, high-contrast modes,
   reduced motion and clearer feedback for users who do not rely on color.
5. **Simpler setup:** a graphical preferences flow, backend checks and microphone
   selection that can be completed without editing configuration files.
6. **Platform coverage:** investigate native Wayland integration and test across
   desktop environments, input methods and languages.
7. **Feedback and validation:** collaborate with users with motor or visual
   impairments, document concrete workflows, reproduce reported problems and
   publish the limits of each tested configuration.

Priorities will follow actual feedback and implementation feasibility.
These are plans, not features already shipped or promises of delivery dates.
