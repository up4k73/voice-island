"""Run only on an isolated X11 display: synthetic PCM, local HTTP, test editor."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import Gtk, GLib, GdkX11, Gdk
import cairo

from voice_island.audio import Capture
from voice_island.config import Config
from voice_island.controller import Controller
from voice_island.output import TextOutput
from voice_island.widget import Island, BAR_STYLES

if os.environ.get("VOICE_ISLAND_ISOLATED_TEST") != "1":
    raise SystemExit("Set VOICE_ISLAND_ISOLATED_TEST=1 inside an isolated test display")

out = Path(os.environ.get("VOICE_ISLAND_TEST_OUTPUT", "artifacts/gui"))
out.mkdir(parents=True, exist_ok=True)
expected = "Привет, Voice Island!"
received = []

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        received.append({'path':self.path, 'wav':b'RIFF' in body and b'WAVE' in body,
                         'multipart':self.headers.get('Content-Type','').startswith('multipart/form-data')})
        payload = json.dumps({'text':expected}).encode()
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
    def log_message(self, *args):
        pass

http = ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=http.serve_forever,daemon=True).start()
config = Config(url=f'http://127.0.0.1:{http.server_port}/transcribe')
view = Island(demo=True)
editor_output=out/'editor.json'
editor_output.unlink(missing_ok=True)
editor=subprocess.Popen([sys.executable,str(Path(__file__).with_name('gtk_editor_fixture.py')),
                         str(editor_output)],stdout=subprocess.PIPE,text=True)
editor_xid=int(editor.stdout.readline().strip())
def editor_text():
    return json.loads(editor_output.read_text())['text'] if editor_output.exists() else ''
copied = []
result = {'synthetic_audio':True,'live_hardware':False,'typing_matches':False}

def dispatch(fn,*args):
    GLib.idle_add(lambda: (fn(*args),False)[1])

emitter = """import math, struct, sys, time
samples=struct.pack('<1024h',*[int(math.sin(i*2*math.pi*64/1024)*20000) for i in range(1024)])
while True:
 sys.stdout.buffer.write(samples); sys.stdout.buffer.flush(); time.sleep(.064)
"""

def fixture_popen(command, **kwargs):
    assert command[0] == 'parec'
    assert '--format=s16le' in command and '--channels=1' in command
    return subprocess.Popen([sys.executable,'-c',emitter],**kwargs)

def copy_ready(value):
    ready=threading.Event()
    def update():
        copied.append(value)
        clipboard=Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(value,-1)
        ready.set()
    dispatch(update)
    if not ready.wait(3):raise RuntimeError('Clipboard unavailable')

controller = Controller(config,view,TextOutput(copy_ready),dispatch,
    capture_factory=lambda *args: Capture(*args,popen=fixture_popen))

def export(name):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,view.PILL_W*2,view.PILL_H*2)
    context = cairo.Context(surface); context.scale(2,2)
    view._draw(view,context)
    surface.write_to_png(str(out/(name+'.png')))

def start():
    subprocess.run(['xdotool','windowfocus','--sync',str(editor_xid)],check=True)
    controller.toggle()
    GLib.timeout_add(900,stop)
    return False

def stop():
    for index,style in enumerate(BAR_STYLES):
        view._style_idx=index
        export(style)
    controller.toggle()
    GLib.timeout_add(100,check_result)
    return False

def check_result():
    actual=editor_text()
    if actual==expected+' ':
        assert received == [{'path':'/transcribe','wav':True,'multipart':True}]
        assert copied == [expected+' ']
        result.update(typing_matches=True,request_count=len(received),focus_preserved=True)
        export('complete')
        Gtk.main_quit()
        return False
    return True

GLib.timeout_add(200,start)
GLib.timeout_add(15000,lambda:(Gtk.main_quit(),False)[1])
try:
    Gtk.main()
finally:
    result.update(actual=editor_text(),clipboard=copied,
                  requests=received,status=view._message,initial_focus=controller.initial_focus,
                  current_focus=controller.output.focus())
    controller.close()
    http.shutdown()
    editor.terminate()
    editor.wait(timeout=3)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
raise SystemExit(0 if result['typing_matches'] else 1)
