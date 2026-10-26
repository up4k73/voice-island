"""Local commands for desktop shortcuts; only this user's session can connect."""
import fcntl
import os
from pathlib import Path
import socket
import tempfile
import threading

COMMANDS = {"toggle", "cancel", "quit"}


def runtime_directory():
    base = Path(os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()))
    path = base / f"voice-island-{os.getuid()}"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or path.stat().st_uid != os.getuid():
        raise RuntimeError("Invalid runtime directory")
    path.chmod(0o700)
    return path


def send(command, directory=None):
    if command not in COMMANDS:
        raise ValueError("Unknown command")
    path = Path(directory) if directory else runtime_directory()
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
        client.settimeout(1)
        client.sendto(command.encode("ascii"), str(path / "control.sock"))


class CommandServer:
    def __init__(self, callback, directory=None):
        self.directory = Path(directory) if directory else runtime_directory()
        self.path = self.directory / "control.sock"
        self.callback = callback
        self.lock = (self.directory / "instance.lock").open("a+")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            raise RuntimeError("Voice Island is already running") from None
        self.path.unlink(missing_ok=True)
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            self.socket.bind(str(self.path))
            self.path.chmod(0o600)
            self.socket.settimeout(0.25)
        except Exception:
            self.socket.close()
            self.lock.close()
            raise
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()

    def _listen(self):
        while not self.stopped.is_set():
            try:
                command = self.socket.recv(128).decode("ascii")
                if command in COMMANDS:
                    self.callback(command)
            except socket.timeout:
                continue
            except UnicodeError:
                continue
            except OSError:
                break

    def close(self):
        self.stopped.set()
        self.socket.close()
        self.thread.join(timeout=1)
        self.path.unlink(missing_ok=True)
        self.lock.close()
