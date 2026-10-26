"""Independent X11 text editor used only by the isolated GUI test."""
import json
import os
from pathlib import Path
import sys

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import Gtk, GdkX11

if os.environ.get("VOICE_ISLAND_ISOLATED_TEST") != "1":
    raise SystemExit("This fixture requires an isolated test display")

destination = Path(sys.argv[1])
window = Gtk.Window(title="Voice Island isolated test editor")
window.set_default_size(600,200)
editor = Gtk.TextView()
window.add(editor)
def changed(buffer):
    value=buffer.get_text(*buffer.get_bounds(),True)
    temporary=destination.with_suffix('.tmp')
    temporary.write_text(json.dumps({'text':value}))
    temporary.replace(destination)
editor.get_buffer().connect('changed',changed)
window.show_all()
editor.grab_focus()
print(window.get_window().get_xid(),flush=True)
Gtk.main()
