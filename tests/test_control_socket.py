import socket
from pathlib import Path
import tempfile
import threading
import unittest

from voice_island.control_socket import CommandServer, send


class SocketTests(unittest.TestCase):
    def test_private_single_instance_and_known_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            received = []
            ready = threading.Event()
            def on_command(command):
                received.append(command)
                ready.set()
            server = CommandServer(on_command,directory)
            try:
                with self.assertRaises(RuntimeError):
                    CommandServer(on_command,directory)
                self.assertEqual((Path(directory)/"control.sock").stat().st_mode & 0o777,0o600)
                send("toggle",directory)
                self.assertTrue(ready.wait(2))
                self.assertEqual(received,["toggle"])
                with self.assertRaises(ValueError): send("execute",directory)
            finally:
                server.close()
            self.assertFalse((Path(directory)/"control.sock").exists())


if __name__ == "__main__":
    unittest.main()
