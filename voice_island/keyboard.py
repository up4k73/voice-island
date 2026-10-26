"""Optional evdev shortcut for an explicitly chosen input device."""
import time

KEY_NAMES = {"pause": 119, "scroll_lock": 70, "print_screen": 99,
             "f9": 67, "f10": 68, "f11": 87, "f12": 88, "insert": 110}


def listen(device_path, key, callback):
    import evdev
    device = evdev.InputDevice(device_path)
    modifiers, last = set(), 0.0
    try:
        for event in device.read_loop():
            if event.type != evdev.ecodes.EV_KEY:
                continue
            if event.code in {29, 97, 56, 100, 42, 54, 125, 126}:
                if event.value:
                    modifiers.add(event.code)
                else:
                    modifiers.discard(event.code)
                continue
            if event.code == KEY_NAMES[key] and event.value == 1 and not modifiers:
                now = time.monotonic()
                if now - last >= 0.3:
                    last = now
                    callback()
    finally:
        device.close()
