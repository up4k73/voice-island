"""Command-line entry point and GTK integration."""
import argparse
import math
import os
from pathlib import Path
import signal
import sys
import threading

from . import __version__
from .config import load, write_example
from .control_socket import CommandServer, send


def parser():
    result = argparse.ArgumentParser(description="Linux dictation with a compact animated recording indicator")
    result.add_argument("--version", action="version", version=__version__)
    actions = result.add_mutually_exclusive_group()
    for action in ("toggle", "cancel", "quit", "preview", "init-config"):
        actions.add_argument("--" + action, action="store_true")
    result.add_argument("--config", type=Path, help="Configuration JSON path")
    for name in ("url", "long-url", "language", "source", "theme", "style", "output"):
        result.add_argument("--" + name)
    result.add_argument("--max-seconds", type=int)
    result.add_argument("--top-offset", type=int)
    result.add_argument("--device", help="Optional evdev keyboard device; desktop shortcuts need no raw input access")
    result.add_argument("--key", default="pause")
    result.add_argument("--preview-image", type=Path, help="Save the preview widget as PNG; requires --preview")
    result.add_argument("--preview-seconds", type=float, default=0, help="Stop preview after this many seconds")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    if args.init_config:
        try:
            print(write_example(args.config))
            return 0
        except OSError as error:
            print(str(error), file=sys.stderr)
            return 1
    if args.preview_image and not args.preview:
        parser().error("--preview-image requires --preview")
    command = next((name for name in ("toggle", "cancel", "quit") if getattr(args, name)), None)
    if command:
        try:
            send(command)
            return 0
        except (FileNotFoundError, ConnectionRefusedError):
            if command != "toggle":
                return 0
    if not args.preview and os.environ.get("XDG_SESSION_TYPE") == "wayland":
        print("This release supports X11 sessions. Native Wayland input is not implemented.", file=sys.stderr)
        return 1
    names = ("url", "long_url", "language", "source", "theme", "style", "output", "max_seconds", "top_offset")
    try:
        config = load(args.config, {name: getattr(args, name) for name in names})
    except (ValueError, TypeError, OSError) as error:
        print(f"Invalid configuration: {error}", file=sys.stderr)
        return 1
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gdk, GLib
    from .widget import Island
    from .controller import Controller
    from .output import TextOutput
    if not Gdk.Display.get_default():
        print("A graphical X11 session is required", file=sys.stderr)
        return 1
    view = Island(config.theme, config.style, config.top_offset, args.preview)

    def dispatch(callback, *arguments):
        def once():
            callback(*arguments)
            return False
        GLib.idle_add(once)

    def copy_text(text):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)
        clipboard.store()

    if args.preview:
        view.show_recording()
        tick = [0]
        def animate():
            tick[0] += 1
            view.push_levels([0.12 + 0.75 * abs(math.sin(i * 0.23 + tick[0] * 0.08)) ** 2 for i in range(view.BAR_COUNT)])
            return True
        GLib.timeout_add(64, animate)
        if args.preview_image:
            def export():
                import cairo
                args.preview_image.parent.mkdir(parents=True, exist_ok=True)
                surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, view.PILL_W * 2, view.PILL_H * 2)
                context = cairo.Context(surface)
                context.scale(2, 2)
                view._draw(view, context)
                surface.write_to_png(str(args.preview_image))
                return False
            GLib.timeout_add(800, export)
        if args.preview_seconds > 0:
            GLib.timeout_add(int(args.preview_seconds * 1000), lambda: (Gtk.main_quit(), False)[1])
        signal.signal(signal.SIGINT, lambda *_: Gtk.main_quit())
        signal.signal(signal.SIGTERM, lambda *_: Gtk.main_quit())
        Gtk.main()
        return 0

    controller = Controller(config, view, TextOutput(lambda text: dispatch(copy_text, text)), dispatch)
    def handle(action):
        if action == "toggle":
            controller.toggle()
        elif action == "cancel":
            controller.cancel()
        elif action == "quit":
            Gtk.main_quit()
    try:
        server = CommandServer(lambda action: dispatch(handle, action))
    except (OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    if args.device:
        from .keyboard import KEY_NAMES, listen
        if args.key not in KEY_NAMES:
            server.close()
            print("Unsupported keyboard key", file=sys.stderr)
            return 1
        def keyboard():
            try:
                listen(args.device, args.key, lambda: dispatch(controller.toggle))
            except Exception:
                dispatch(view.show_message, "Keyboard unavailable — use shortcut", True)
        threading.Thread(target=keyboard, daemon=True).start()
    signal.signal(signal.SIGINT, lambda *_: Gtk.main_quit())
    signal.signal(signal.SIGTERM, lambda *_: Gtk.main_quit())
    signal.signal(signal.SIGUSR1, lambda *_: dispatch(controller.toggle))
    if command == "toggle":
        dispatch(controller.toggle)
    else:
        view.show_message("Ready — use your shortcut")
    try:
        Gtk.main()
    finally:
        controller.close()
        server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
