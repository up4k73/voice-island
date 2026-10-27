"""Dictation states are serialized on the UI thread."""
import threading

from .audio import Capture, RATE
from .transcription import transcribe


def background(work):
    threading.Thread(target=work, daemon=True).start()


class Controller:
    def __init__(self, config, view, output, dispatch, capture_factory=Capture,
                 recognize=transcribe, submit=background):
        self.config, self.view, self.output = config, view, output
        self.dispatch, self.capture_factory = dispatch, capture_factory
        self.recognize, self.submit = recognize, submit
        self.state = "idle"
        self.capture = None
        self.pending_capture = None
        self.generation = 0
        self.initial_focus = None
        self.closed = False

    def toggle(self):
        if self.closed or self.state == "processing":
            return
        if self.state == "recording":
            self.stop()
            return
        self.generation += 1
        generation = self.generation
        self.initial_focus = self.output.focus()
        self.capture = self.capture_factory(self.config,
            lambda levels: self.dispatch(self._levels, generation, levels),
            lambda: self.dispatch(self._limit, generation),
            lambda message: self.dispatch(self._capture_failed, generation, message))
        self.state = "recording"
        self.view.show_recording()
        try:
            self.capture.start()
        except Exception:
            self.cancel()
            self.view.show_message("Cannot start microphone", error=True)

    def _levels(self, generation, levels):
        if generation == self.generation and self.state == "recording":
            self.view.push_levels(levels)

    def _limit(self, generation):
        if generation == self.generation and self.state == "recording":
            self.stop()

    def _capture_failed(self, generation, message):
        if generation == self.generation and self.state == "recording":
            self.cancel()
            self.view.show_message(message, error=True)

    def stop(self):
        if self.state != "recording":
            return
        self.state = "processing"
        self.view.show_processing()
        capture, self.capture = self.capture, None
        self.pending_capture = capture
        generation, focus = self.generation, self.initial_focus

        def work():
            try:
                pcm = capture.stop()
                self.pending_capture = None
                if len(pcm) < RATE // 2:
                    self.dispatch(self._result, generation, "", focus, "Recording too short")
                    return
                if generation != self.generation or self.closed:
                    return
                text = self.recognize(pcm, self.config)
                self.dispatch(self._result, generation, text, focus, None)
            except Exception as error:
                # Do not expose URLs, tokens, server response bodies or transcripts.
                message = str(error) if isinstance(error, RuntimeError) and str(error).startswith("Speech service returned HTTP ") else "Speech recognition failed"
                self.dispatch(self._result, generation, "", focus, message)

        self.submit(work)

    def _result(self, generation, text, focus, error):
        if generation != self.generation or self.closed:
            return
        self.state = "idle"
        if error:
            self.view.show_message(error, error=True)
        elif not text:
            self.view.show_message("No speech recognized")
        else:
            self.state = "processing"
            def deliver():
                if generation != self.generation or self.closed:
                    return
                message = self.output.deliver(text, focus, self.config.output,
                    is_cancelled=lambda: generation != self.generation or self.closed,
                    paste_shortcut=self.config.paste_shortcut)
                self.dispatch(self._delivered, generation, message)
            self.submit(deliver)

    def _delivered(self, generation, message):
        if generation == self.generation and not self.closed:
            self.state = "idle"
            self.view.show_message(message)

    def cancel(self):
        self.generation += 1
        self.output.cancel()
        self.state = "idle"
        capture, self.capture = self.capture, None
        if capture:
            def stop_capture():
                try:
                    capture.stop()
                except Exception:
                    pass
            self.submit(stop_capture)
        self.view.hide_island()

    def close(self):
        self.closed = True
        self.generation += 1
        self.output.cancel()
        for capture in (self.capture, self.pending_capture):
            if capture is not None:
                try:
                    capture.stop()
                except Exception:
                    pass
        self.capture = self.pending_capture = None
        self.state = "idle"
        self.view.hide_island()
