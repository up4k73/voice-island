"""A single PulseAudio-compatible stream supplies recording and FFT levels."""
import io
import subprocess
import threading
import wave

import numpy as np

RATE = 16000
CHUNK = 1024
BAR_COUNT = 32


def wave_bytes(pcm):
    if len(pcm) % 2:
        raise ValueError("Incomplete PCM sample")
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(RATE)
        stream.writeframes(pcm)
    return output.getvalue()


class Spectrum:
    def __init__(self, floor_db=-60):
        self.floor_db = floor_db
        self.window = np.hanning(CHUNK).astype(np.float32)
        edges = np.logspace(np.log10(120), np.log10(7500), BAR_COUNT + 1)
        self.edges = np.clip((edges * CHUNK / RATE).astype(int), 0, CHUNK // 2)

    def levels(self, pcm):
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
        samples = np.pad(samples[:CHUNK], (0, max(0, CHUNK - len(samples))))
        spectrum = np.abs(np.fft.rfft(samples * self.window))
        bands = [float(np.max(spectrum[lo:max(lo + 1, hi)])) for lo, hi in zip(self.edges, self.edges[1:])]
        # A full-scale bin-centered sine through a Hann window is about N/4.
        db = 20 * np.log10(np.maximum(bands, 1e-9) / (CHUNK / 4))
        return np.clip((db - self.floor_db) / -self.floor_db, 0, 1).tolist()


class Capture:
    def __init__(self, config, on_levels, on_limit, on_failure, popen=subprocess.Popen):
        self.config, self.on_levels = config, on_levels
        self.on_limit, self.on_failure, self.popen = on_limit, on_failure, popen
        self.process = None
        self.thread = None
        self.stopping = threading.Event()
        self.buffer = bytearray()
        self.error = None
        self.stop_lock = threading.Lock()

    def start(self):
        command = ["parec", "--format=s16le", f"--rate={RATE}", "--channels=1", "--latency-msec=1"]
        if self.config.source:
            command += ["--device", self.config.source]
        self.process = self.popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        spectrum = Spectrum(self.config.meter_floor_db)
        maximum = self.config.max_seconds * RATE * 2
        try:
            while not self.stopping.is_set():
                raw = self.process.stdout.read(CHUNK * 2)
                if not raw:
                    if not self.stopping.is_set():
                        raise RuntimeError("Microphone stream ended")
                    break
                raw = raw[:maximum - len(self.buffer)]
                self.buffer.extend(raw)
                if len(raw) % 2 == 0:
                    self.on_levels(spectrum.levels(raw))
                if len(self.buffer) >= maximum:
                    self.on_limit()
                    break
        except Exception:
            self.error = "Microphone capture failed"
            if not self.stopping.is_set():
                self.on_failure(self.error)

    def stop(self):
        with self.stop_lock:
            return self._stop()

    def _stop(self):
        self.stopping.set()
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
            if self.thread is not None and self.thread is not threading.current_thread():
                self.thread.join(timeout=3)
            self.process.stdout.close()
        if self.thread is not None and self.thread.is_alive():
            raise RuntimeError("Microphone did not stop")
        if self.error:
            raise RuntimeError(self.error)
        pcm = bytes(self.buffer)
        self.buffer.clear()
        return pcm
