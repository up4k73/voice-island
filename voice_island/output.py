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

    def copy_status(self, text, message):
        try:
            self.copy_text(text)
            return message
        except Exception:
            return "Clipboard unavailable"

    def deliver(self, text, initial_focus, mode="paste", is_cancelled=lambda: False, paste_shortcut="ctrl+v"):
        with self.lock:
            self.cancel_requested = False
        def aborted():
            return self.cancel_requested or is_cancelled()
        if aborted():
            return "Cancelled"
        if mode == "clipboard":
            return self.copy_status(text,"Copied to clipboard")
        if initial_focus is None or self.focus() != initial_focus:
            return self.copy_status(text,"Focus changed — copied")
        process = None
        try:
            if mode == "paste":
                if self.copy_status(text + " ","ready") != "ready":return "Clipboard unavailable"
                if aborted():return "Cancelled"
                if self.focus() != initial_focus:return "Focus changed — copied"
                command=["xdotool","key","--clearmodifiers",paste_shortcut]
                payload=""
            else:
                command=["xdotool", "type", "--clearmodifiers", "--delay", "12", "--file", "-"]
                payload=text + " "
            process = self.popen(command,
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8")
            with self.lock:
                self.process = process
            if aborted():
                process.terminate()
            process.communicate(input="" if aborted() else payload, timeout=max(30, min(180, len(text) * 0.024 + 5)))
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
            return self.copy_status(text,"Insertion failed — copied")
        finally:
            with self.lock:
                if self.process is process:
                    self.process = None
        return "Text inserted"
