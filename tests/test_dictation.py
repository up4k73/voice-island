import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock
import wave

import numpy as np

from voice_island.audio import CHUNK, RATE, Spectrum, wave_bytes
from voice_island.config import Config, load, write_example
from voice_island.controller import Controller
from voice_island.output import TextOutput
from voice_island.transcription import transcribe


class ConfigTests(unittest.TestCase):
    def test_portable_defaults_and_override(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            write_example(path)
            self.assertEqual(load(path, {"theme": "ice"}).theme, "ice")
            self.assertEqual(load(path).url, "http://127.0.0.1:9875/transcribe")
            with self.assertRaises(FileExistsError):
                write_example(path)

    def test_reject_unsafe_or_invalid_configuration(self):
        for values in [{"url":"file:///tmp/audio"}, {"url":"https://user:password@example.test/transcribe"},
                       {"max_seconds":0}, {"style":"missing"}, {"output":"shell"}, {"meter_floor_db":0}]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                Config(**values).validate()


class AudioTests(unittest.TestCase):
    def test_wave_is_mono_pcm16_at_16khz(self):
        pcm = b"\0\0" * RATE
        with wave.open(io.BytesIO(wave_bytes(pcm))) as audio:
            self.assertEqual((audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes()), (1,2,RATE,RATE))
            self.assertEqual(audio.readframes(RATE), pcm)
        with self.assertRaises(ValueError):
            wave_bytes(b"\0")

    def test_spectrum_silence_and_sine_scale(self):
        spectrum = Spectrum()
        self.assertEqual(spectrum.levels(b"\0\0" * CHUNK), [0.0] * 32)
        samples = (np.sin(np.arange(CHUNK) * 2 * np.pi * 64 / CHUNK) * 32767).astype("<i2")
        values = spectrum.levels(samples.tobytes())
        self.assertGreater(max(values), 0.98)
        self.assertTrue(all(0 <= value <= 1 for value in values))


class TranscriptionTests(unittest.TestCase):
    def response(self, status=200, data=None):
        response = Mock(status_code=status)
        response.json.return_value = {"text":"hello"} if data is None else data
        return response

    def test_explicit_endpoint_and_full_audio_with_no_redirects(self):
        response = self.response(data={"text":" hello\nworld\t! "})
        post = Mock(return_value=response)
        result = transcribe(b"\0\0" * RATE, Config(), post)
        self.assertEqual(result, "hello world !")
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.args, (Config().url,))
        self.assertFalse(post.call_args.kwargs["allow_redirects"])
        with wave.open(io.BytesIO(post.call_args.kwargs["files"]["file"][1])) as audio:
            self.assertEqual(audio.getnframes(), RATE)
        response.close.assert_called_once()

    def test_long_endpoint_only_when_explicitly_configured(self):
        post = Mock(return_value=self.response())
        config = Config(long_url="http://127.0.0.1:9875/transcribe_long")
        transcribe(b"\0\0" * RATE * 26, config, post)
        self.assertEqual(post.call_args.args[0], config.long_url)
        transcribe(b"\0\0" * RATE * 26, Config(), post)
        self.assertEqual(post.call_args.args[0], Config().url)

    def test_http_failure_invalid_body_and_redirect_do_not_retry(self):
        for status, data in [(500,{}),(302,{}),(200,{"text":123}),(200,[])]:
            response = self.response(status, data)
            post = Mock(return_value=response)
            with self.subTest(status=status,data=data), self.assertRaises((RuntimeError,ValueError)):
                transcribe(b"\0\0" * RATE, Config(), post)
            self.assertEqual(post.call_count,1)
            response.close.assert_called_once()


class OutputTests(unittest.TestCase):
    def test_text_goes_via_stdin_and_only_to_unchanged_focus(self):
        run = Mock(return_value=Mock(stdout="123\n"))
        process=Mock(returncode=0)
        popen=Mock(return_value=process)
        output = TextOutput(Mock(), run, popen)
        self.assertEqual(output.deliver("text $() ; literal", "123"), "Text inserted")
        self.assertEqual(popen.call_args.args[0][-2:], ["--file","-"])
        self.assertEqual(process.communicate.call_args.kwargs["input"], "text $() ; literal ")
        self.assertNotIn("text $() ; literal", popen.call_args.args[0])

    def test_cancellation_stops_typing_and_does_not_copy(self):
        run=Mock(return_value=Mock(stdout="123"))
        copy=Mock()
        process=Mock(returncode=-15)
        process.poll.return_value=None
        output=TextOutput(copy,run,Mock(return_value=process))
        process.communicate.side_effect=lambda **kwargs: output.cancel()
        self.assertEqual(output.deliver("cancel this", "123"),"Cancelled")
        process.terminate.assert_called_once()
        copy.assert_not_called()

    def test_focus_change_falls_back_to_clipboard_without_typing(self):
        run, copy = Mock(return_value=Mock(stdout="456")), Mock()
        self.assertEqual(TextOutput(copy,run).deliver("hello", "123"), "Focus changed — copied")
        copy.assert_called_once_with("hello")
        self.assertEqual(run.call_count, 1)

    def test_clipboard_mode_does_not_invoke_keyboard_tools(self):
        run, copy = Mock(), Mock()
        TextOutput(copy,run).deliver("hello", None, "clipboard")
        run.assert_not_called()
        copy.assert_called_once_with("hello")


class ControllerTests(unittest.TestCase):
    def setup_controller(self):
        view, output = Mock(), Mock()
        output.focus.return_value = "123"
        output.deliver.return_value = "Text inserted"
        capture = Mock()
        capture.stop.return_value = b"\0\0" * RATE
        jobs = []
        recognize = Mock(return_value="hello")
        controller = Controller(Config(), view, output, lambda fn,*a:fn(*a),
            capture_factory=Mock(return_value=capture), recognize=recognize, submit=jobs.append)
        return controller, view, output, capture, jobs, recognize

    def test_toggle_records_then_transcribes_once(self):
        controller, view, output, capture, jobs, recognize = self.setup_controller()
        controller.toggle()
        self.assertEqual(controller.state,"recording")
        capture.start.assert_called_once()
        controller.toggle()
        self.assertEqual(controller.state,"processing")
        controller.toggle()
        self.assertEqual(len(jobs),1)
        jobs.pop(0)()
        recognize.assert_called_once()
        self.assertEqual(controller.state,"processing")
        jobs.pop(0)()
        self.assertEqual(output.deliver.call_args.args,("hello","123","type"))
        self.assertFalse(output.deliver.call_args.kwargs['is_cancelled']())
        self.assertEqual(controller.state,"idle")

    def test_cancelled_result_never_types(self):
        controller, view, output, capture, jobs, recognize = self.setup_controller()
        controller.toggle()
        controller.toggle()
        controller.cancel()
        jobs.pop(0)()
        output.deliver.assert_not_called()
        recognize.assert_not_called()

    def test_empty_or_failed_transcription_does_not_type_or_log_content(self):
        for result in ["", RuntimeError("secret endpoint or transcript")]:
            controller, view, output, capture, jobs, recognize = self.setup_controller()
            if isinstance(result, Exception): recognize.side_effect = result
            else: recognize.return_value = result
            controller.toggle(); controller.toggle(); jobs.pop(0)()
            output.deliver.assert_not_called()
            self.assertNotIn("secret", str(view.show_message.call_args))
            self.assertEqual(controller.state,"idle")

    def test_close_stops_microphone_synchronously(self):
        controller, view, output, capture, jobs, recognize = self.setup_controller()
        controller.toggle()
        controller.close()
        capture.stop.assert_called_once()
        self.assertTrue(controller.closed)
        controller.toggle()
        self.assertEqual(capture.start.call_count,1)

    def test_cancel_between_recognition_and_delivery_drops_text(self):
        controller, view, output, capture, jobs, recognize = self.setup_controller()
        controller.toggle(); controller.toggle(); jobs.pop(0)()
        controller.cancel(); jobs.pop(0)()
        output.deliver.assert_not_called()


if __name__ == "__main__":
    unittest.main()
