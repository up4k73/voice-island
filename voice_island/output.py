"""Focused-window insertion keeps transcript text out of process arguments."""
import subprocess
import threading


class TextOutput:
    def __init__(self, copy_text, run=subprocess.run, popen=subprocess.Popen):
        self.copy_text, self.run, self.popen = copy_text, run, popen
        self.lock = threading.Lock()
        self.process = None
        self.cancel_requested = False

    def focus(self):
        try:
            result = self.run(["xdotool", "getwindowfocus"], capture_output=True,
                              text=True, check=True, timeout=2)
            value = result.stdout.strip()
            return value if value.isdigit() and int(value) > 1 else None
        except (OSError, subprocess.SubprocessError):
            return None

    def cancel(self):
        with self.lock:
            self.cancel_requested = True
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()

    def deliver(self, text, initial_focus, mode="type", is_cancelled=lambda: False):
        with self.lock:
            self.cancel_requested = False
        def aborted():
            return self.cancel_requested or is_cancelled()
        if aborted():
            return "Cancelled"
        if mode == "clipboard":
            self.copy_text(text)
            return "Copied to clipboard"
        if initial_focus is None or self.focus() != initial_focus:
            self.copy_text(text)
            return "Focus changed — copied"
        process = None
        try:
            process = self.popen(["xdotool", "type", "--clearmodifiers", "--delay", "12", "--file", "-"],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8")
            with self.lock:
                self.process = process
            if aborted():
                process.terminate()
            process.communicate(input="" if aborted() else text + " ", timeout=max(30, min(180, len(text) * 0.024 + 5)))
            if aborted():
                return "Cancelled"
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, "xdotool")
        except (OSError, subprocess.SubprocessError):
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=2)
            if aborted():
                return "Cancelled"
            self.copy_text(text)
            return "Typing failed — copied"
        finally:
            with self.lock:
                if self.process is process:
                    self.process = None
        return "Text inserted"
