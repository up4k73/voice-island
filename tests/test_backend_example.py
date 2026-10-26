import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import wave

import requests

from examples.gigaam_server import transcribe_request
from voice_island.audio import RATE, wave_bytes


class BackendTests(unittest.TestCase):
    def request(self, audio):
        request = requests.Request("POST","http://127.0.0.1/transcribe",
            files={"file":("audio.wav",audio,"audio/wav")},data={"language":"ru"}).prepare()
        return request.body,request.headers["Content-Type"]

    def test_valid_upload_and_temporary_file_cleanup(self):
        paths=[]
        def recognize(filename):
            path=Path(filename);self.assertTrue(path.exists());paths.append(path)
            with wave.open(filename) as audio:self.assertEqual(audio.getnframes(),RATE)
            return SimpleNamespace(text=" test ")
        self.assertEqual(transcribe_request(*self.request(wave_bytes(b"\0\0"*RATE)),Mock(transcribe=recognize)),"test")
        self.assertFalse(paths[0].exists())

    def test_long_recording_rejected_before_model(self):
        model=Mock()
        with self.assertRaises(ValueError):
            transcribe_request(*self.request(wave_bytes(b"\0\0"*RATE*26)),model)
        model.transcribe.assert_not_called()

    def test_failed_recognition_removes_temporary_audio(self):
        paths=[]
        def recognize(filename):
            paths.append(Path(filename));raise RuntimeError("Model failed")
        with self.assertRaises(RuntimeError):
            transcribe_request(*self.request(wave_bytes(b"\0\0"*RATE)),Mock(transcribe=recognize))
        self.assertFalse(paths[0].exists())
