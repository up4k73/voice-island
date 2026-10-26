"""The original compact recording indicator, independent of personal services."""
import math
import colorsys

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Gdk, GLib, Pango, PangoCairo

BAR_STYLES   = ["solid", "blocks", "bounce", "dots"]

THEMES = [
    {"name": "matrix",   "bg": (0.02, 0.05, 0.02),  "hue_lo": 108, "hue_hi": 140,
     "border": (0.10, 0.88, 0.10),  "shimmer": 0.0, "sat": 0.78},
    {"name": "fire",     "bg": (0.07, 0.01, 0.01),  "hue_lo":   2, "hue_hi":  52,
     "border": (0.92, 0.40, 0.02),  "shimmer": 0.0, "sat": 0.94},
    {"name": "electric", "bg": (0.02, 0.04, 0.10),  "hue_lo": 185, "hue_hi": 215,
     "border": (0.10, 0.72, 1.00),  "shimmer": 3.5, "sat": 0.85},
    {"name": "plasma",   "bg": (0.06, 0.01, 0.09),  "hue_lo": 268, "hue_hi": 318,
     "border": (0.80, 0.20, 1.00),  "shimmer": 1.8, "sat": 0.82},
    {"name": "ice",      "bg": (0.03, 0.04, 0.09),  "hue_lo": 198, "hue_hi": 228,
     "border": (0.50, 0.82, 1.00),  "shimmer": 0.6, "sat": 0.58},
]

def _pill(cr, w, h, r):
    cr.new_sub_path()
    cr.arc(w - r, r,     r, -math.pi / 2, 0)
    cr.arc(w - r, h - r, r, 0,            math.pi / 2)
    cr.arc(r,     h - r, r, math.pi / 2,  math.pi)
    cr.arc(r,     r,     r, math.pi,      3 * math.pi / 2)
    cr.close_path()

def _rrect(cr, x, y, w, h, r=2):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + r,     y + r,     r, math.pi,          3 * math.pi / 2)
    cr.arc(x + w - r, y + r,     r, 3 * math.pi / 2,  0)
    cr.arc(x + w - r, y + h - r, r, 0,                math.pi / 2)
    cr.arc(x + r,     y + h - r, r, math.pi / 2,      math.pi)
    cr.close_path()

class Island(Gtk.Window):
    PILL_H = 50
    RADIUS = 25
    BAR_COUNT = 32
    BAR_W = 4
    BAR_GAP = 2
    BADGE_W = 58
    MARGIN = 11

    @property
    def PILL_W(self):
        return self.MARGIN * 2 + self.BAR_COUNT * (self.BAR_W + self.BAR_GAP) - self.BAR_GAP + self.BADGE_W

    @property
    def _theme(self):
        return THEMES[self._theme_idx]

    def __init__(self, theme="electric", style="solid", top_offset=8, demo=False):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_title("Voice Island")
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_accept_focus(False)
        self.set_focus_on_map(False)
        self.set_app_paintable(True)
        self.set_default_size(self.PILL_W, self.PILL_H)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.connect("draw", self._draw)
        self._theme_idx = next(i for i, item in enumerate(THEMES) if item["name"] == theme)
        self._style_idx = BAR_STYLES.index(style)
        self._top_offset = top_offset
        self._demo = demo
        self._pulse = 0
        self._state = "hidden"
        self._message = ""
        self._error = False
        self._timer = None
        self._hide_timer = None
        self._reset_levels()

    def _reset_levels(self):
        self._levels = [0.0] * self.BAR_COUNT
        self._peaks = [0.0] * self.BAR_COUNT
        self._peak_age = [0] * self.BAR_COUNT
        self._pos = [0.0] * self.BAR_COUNT
        self._vel = [0.0] * self.BAR_COUNT
        self._trails = [[] for _ in range(self.BAR_COUNT)]
        self._sparks = []

    def _place(self):
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        geometry = monitor.get_geometry()
        self.move(geometry.x + (geometry.width - self.PILL_W) // 2,
                  geometry.y + self._top_offset)

    def push_levels(self, levels):
        for i, target in enumerate(levels[:self.BAR_COUNT]):
            target = max(0.0, min(1.0, target))
            current = self._levels[i]
            attack = 0.80 + 0.12 * abs(math.sin(i * 0.7))
            decay = 0.06 + 0.04 * abs(math.cos(i * 0.9))
            self._levels[i] = current + (target - current) * attack if target > current else current * (1 - decay)
            level, peak = self._levels[i], self._peaks[i]
            if level >= peak:
                self._peaks[i], self._peak_age[i] = level, 0
                if level > 0.75 and level > peak + 0.05:
                    self._spawn_sparks(i, level)
            else:
                self._peak_age[i] += 1
                if self._peak_age[i] > 30:
                    self._peaks[i] = max(0.0, peak - 0.018)

    def _draw(self, widget, cr):
        width, height = self.get_size()
        cr.set_operator(0)
        cr.paint()
        cr.set_operator(2)
        if self._state == "recording":
            self._bg(cr, width, height)
            self._draw_bars(cr, height)
            self._draw_sparks(cr)
            self._draw_badge(cr, width, height)
        elif self._state == "processing":
            self._bg_processing(cr, width, height)
            self._draw_spinner(cr, height)
            self._draw_label(cr, height, "Transcribing…", 48)
        elif self._state == "message":
            self._bg_processing(cr, width, height)
            self._draw_label(cr, height, self._message, 14)

    def _draw_badge(self, cr, width, height):
        cr.save()
        _pill(cr, width, height, self.RADIUS)
        cr.clip()
        cx = width - self.BADGE_W + 10
        cr.set_source_rgba(*self._theme["border"], 0.92)
        cr.arc(cx, height / 2, 4 + 1.4 * math.sin(self._pulse * 0.28), 0, 2 * math.pi)
        cr.fill()
        layout = self.create_pango_layout("DEMO" if self._demo else "REC")
        layout.set_font_description(Pango.FontDescription("Sans Bold 8"))
        _, text_height = layout.get_pixel_size()
        cr.set_source_rgba(1, 1, 1, 0.70)
        cr.move_to(cx + 8, (height - text_height) / 2)
        PangoCairo.show_layout(cr, layout)
        cr.restore()

    def _draw_label(self, cr, height, text, x):
        layout = self.create_pango_layout(text)
        layout.set_font_description(Pango.FontDescription("Sans Bold 11"))
        layout.set_width((self.PILL_W - x - 12) * Pango.SCALE)
        layout.set_ellipsize(Pango.EllipsizeMode.END)
        _, text_height = layout.get_pixel_size()
        color = (1.0, 0.65, 0.45) if self._error else (0.93, 0.96, 1.0)
        cr.set_source_rgba(*color, 0.95)
        cr.move_to(x, (height - text_height) / 2)
        PangoCairo.show_layout(cr, layout)

    def _tick(self):
        self._pulse += 1
        self.queue_draw()
        return True

    def _show(self, accessible_name):
        if self._hide_timer:
            GLib.source_remove(self._hide_timer)
            self._hide_timer = None
        self.get_accessible().set_name(accessible_name)
        self.set_tooltip_text(accessible_name)
        self._place()
        self.show_all()
        self.queue_draw()
        if self._timer is None:
            self._timer = GLib.timeout_add(33, self._tick)

    def show_recording(self):
        self._reset_levels()
        self._pulse, self._error, self._state = 0, False, "recording"
        self._show("Preview — no microphone" if self._demo else "Recording")

    def show_processing(self):
        self._state, self._error = "processing", False
        self._show("Transcribing")

    def show_message(self, text, error=False):
        self._message, self._error, self._state = text, error, "message"
        self._show(text)
        self._hide_timer = GLib.timeout_add(5000 if error else 2000, self.hide_island)

    def hide_island(self):
        self._state = "hidden"
        self.hide()
        if self._timer is not None:
            GLib.source_remove(self._timer)
            self._timer = None
        if self._hide_timer:
            GLib.source_remove(self._hide_timer)
            self._hide_timer = None
        return False

    def _spawn_sparks(self, bar_idx, lv):
        import random
        rr, gg, bb = self._bar_color(bar_idx, 1.0)
        x0 = self.MARGIN + bar_idx * (self.BAR_W + self.BAR_GAP) + self.BAR_W // 2
        inner_h = self.PILL_H - 12
        y0 = (self.PILL_H - int(inner_h * lv)) // 2
        for _ in range(random.randint(3, 6)):
            vx = random.uniform(-1.2, 1.2)
            vy = random.uniform(-2.5, -0.8)
            life = random.uniform(0.6, 1.0)
            self._sparks.append([x0, y0, vx, vy, life, rr, gg, bb])

    def _update_sparks(self):
        alive = []
        for s in self._sparks:
            s[0] += s[2]          # x += vx
            s[1] += s[3]          # y += vy
            s[3] += 0.18          # gravity
            s[4] -= 0.06          # fade
            if s[4] > 0:
                alive.append(s)
        self._sparks = alive

    def _bar_color(self, i, lv):
        """Return (r,g,b) for bar i at level lv using current theme."""
        t   = self._theme
        lo, hi = t["hue_lo"], t["hue_hi"]
        span   = hi - lo
        # shimmer: gentle oscillation within the hue range
        if t["shimmer"] > 0:
            offset = span * 0.18 * math.sin(self._pulse * t["shimmer"] * 0.04)
        else:
            offset = 0.0
        hue = lo + (i / (self.BAR_COUNT - 1)) * span + offset
        sat = t["sat"] * (0.65 + 0.35 * lv)
        val = 0.22 + 0.78 * lv
        return colorsys.hsv_to_rgb(hue / 360.0 % 1.0, sat, val)

    def _bg(self, cr, w, h):
        t = self._theme
        avg = sum(self._levels) / self.BAR_COUNT
        cr.set_source_rgba(*t["bg"], 0.97); _pill(cr, w, h, self.RADIUS); cr.fill()
        br, bg_, bb = t["border"]
        glow = 0.15 + 0.35 * avg
        cr.set_source_rgba(br, bg_, bb, glow)
        cr.set_line_width(1.5)
        _pill(cr, w, h, self.RADIUS); cr.stroke()

    def _bg_processing(self, cr, w, h):
        cr.set_source_rgba(0.07, 0.07, 0.08, 0.97)
        _pill(cr, w, h, self.RADIUS); cr.fill()
        t = self._theme
        br, bg_, bb = t["border"]
        cr.set_source_rgba(br, bg_, bb, 0.22)
        cr.set_line_width(1.5)
        _pill(cr, w, h, self.RADIUS); cr.stroke()

    def _draw_bars(self, cr, h):
        style = BAR_STYLES[self._style_idx]
        if style == "solid":
            self._bars_solid(cr, h)
        elif style == "blocks":
            self._bars_blocks(cr, h)
        elif style == "bounce":
            self._bars_bounce(cr, h)
        elif style == "dots":
            self._bars_dots(cr, h)

    def _bars_solid(self, cr, h):
        inner_h = h - 12
        mid_y   = h / 2
        x0      = self.MARGIN
        for i in range(self.BAR_COUNT):
            lv = self._levels[i]
            pk = self._peaks[i]
            x  = x0 + i * (self.BAR_W + self.BAR_GAP)
            rr, gg, bb = self._bar_color(i, lv)
            half_h = max(2, int(inner_h / 2 * lv))
            top_y  = mid_y - half_h
            full_h = half_h * 2
            # glow
            cr.set_source_rgba(rr, gg, bb, 0.06 + 0.16 * lv)
            _rrect(cr, x - 2, top_y - 1, self.BAR_W + 4, full_h + 2, 2); cr.fill()
            # bar
            cr.set_source_rgba(rr, gg, bb, 0.88 + 0.12 * lv)
            _rrect(cr, x, top_y, self.BAR_W, max(2, full_h), 1); cr.fill()
            # hot caps
            if half_h > 4 and lv > 0.38:
                mix = min(1.0, (lv - 0.38) / 0.62)
                cap = min(4, half_h // 3)
                cr.set_source_rgba(rr+(1-rr)*mix*.9, gg+(1-gg)*mix*.9, bb+(1-bb)*mix*.9, 0.90)
                _rrect(cr, x, top_y, self.BAR_W, cap, 1); cr.fill()
                _rrect(cr, x, top_y + full_h - cap, self.BAR_W, cap, 1); cr.fill()
            # peak markers
            if pk > 0.05:
                pr, pg, pb = self._bar_color(i, 1.0)
                pkh = max(2, int(inner_h / 2 * pk))
                cr.set_source_rgba(pr, pg, pb, 0.78)
                cr.rectangle(x, mid_y - pkh - 1, self.BAR_W, 2); cr.fill()
                cr.rectangle(x, mid_y + pkh - 1, self.BAR_W, 2); cr.fill()

    def _bars_blocks(self, cr, h):
        """Classic segmented LED VU meter — stacked blocks with gaps."""
        inner_h  = h - 10
        mid_y    = h / 2
        x0       = self.MARGIN
        SEG_H    = 4    # block height
        SEG_GAP  = 1    # gap between blocks
        UNIT     = SEG_H + SEG_GAP
        MAX_SEGS = (inner_h // 2) // UNIT

        for i in range(self.BAR_COUNT):
            lv   = self._levels[i]
            pk   = self._peaks[i]
            x    = x0 + i * (self.BAR_W + self.BAR_GAP)
            segs = max(1, int(MAX_SEGS * lv))
            pksg = max(1, int(MAX_SEGS * pk))
            rr, gg, bb = self._bar_color(i, lv)

            for s in range(segs):
                seg_frac = s / max(1, MAX_SEGS - 1)
                brightness = 0.55 + 0.45 * seg_frac   # brighter towards top
                cr.set_source_rgba(rr * brightness, gg * brightness, bb * brightness, 0.92)
                # top half
                sy_top = mid_y - (s + 1) * UNIT + SEG_GAP
                _rrect(cr, x, sy_top, self.BAR_W, SEG_H, 1); cr.fill()
                # bottom half (mirror)
                sy_bot = mid_y + s * UNIT
                _rrect(cr, x, sy_bot, self.BAR_W, SEG_H, 1); cr.fill()

            # peak segment (bright)
            if pk > 0.05 and pksg > segs:
                pr, pg, pb = self._bar_color(i, 1.0)
                cr.set_source_rgba(pr, pg, pb, 0.90)
                sy = mid_y - pksg * UNIT + SEG_GAP
                _rrect(cr, x, sy, self.BAR_W, SEG_H, 1); cr.fill()
                sy = mid_y + (pksg - 1) * UNIT
                _rrect(cr, x, sy, self.BAR_W, SEG_H, 1); cr.fill()

    def _bars_bounce(self, cr, h):
        """Spring-physics bars that overshoot and oscillate. Upward only."""
        inner_h = h - 10
        x0      = self.MARGIN
        SPRING  = 0.28    # spring constant
        DAMP    = 0.62    # damping (< 1 = bouncy)

        for i in range(self.BAR_COUNT):
            target     = self._levels[i]
            self._vel[i] = (self._vel[i] + (target - self._pos[i]) * SPRING) * DAMP
            self._pos[i] = max(0.0, min(1.25, self._pos[i] + self._vel[i]))  # allow overshoot to 125%

            lv  = min(1.0, self._pos[i])
            pk  = self._peaks[i]
            x   = x0 + i * (self.BAR_W + self.BAR_GAP)
            rr, gg, bb = self._bar_color(i, lv)

            bar_h = max(2, int(inner_h * lv))
            by    = h - 6 - bar_h    # grows upward from bottom

            # glow
            cr.set_source_rgba(rr, gg, bb, 0.07 + 0.17 * lv)
            _rrect(cr, x - 2, by - 1, self.BAR_W + 4, bar_h + 2, 2); cr.fill()
            # bar
            cr.set_source_rgba(rr, gg, bb, 0.90)
            _rrect(cr, x, by, self.BAR_W, bar_h, 1); cr.fill()
            # hot cap
            if bar_h > 4 and lv > 0.35:
                mix = min(1.0, (lv - 0.35) / 0.65)
                cap = min(5, bar_h // 4)
                cr.set_source_rgba(rr+(1-rr)*mix, gg+(1-gg)*mix, bb+(1-bb)*mix, 0.88)
                _rrect(cr, x, by, self.BAR_W, cap, 1); cr.fill()
            # peak
            if pk > 0.05:
                pr, pg, pb = self._bar_color(i, 1.0)
                pk_y = h - 6 - int(inner_h * pk) - 2
                cr.set_source_rgba(pr, pg, pb, 0.80)
                cr.rectangle(x, pk_y, self.BAR_W, 2); cr.fill()

    def _bars_dots(self, cr, h):
        """Glowing leading dot + fading trail. No solid bar."""
        inner_h = h - 12
        mid_y   = h / 2
        x0      = self.MARGIN
        DOT_R   = 2.8

        for i in range(self.BAR_COUNT):
            lv  = self._levels[i]
            x   = x0 + i * (self.BAR_W + self.BAR_GAP) + self.BAR_W / 2
            rr, gg, bb = self._bar_color(i, max(lv, 0.3))

            dot_y_top = mid_y - inner_h / 2 * lv
            dot_y_bot = mid_y + inner_h / 2 * lv

            # update trail for this bar
            trail = self._trails[i]
            trail.append((dot_y_top, dot_y_bot, 1.0))
            # age and prune trail
            self._trails[i] = [(yt, yb, a - 0.12) for yt, yb, a in trail if a > 0.05]

            # draw trail
            for yt, yb, alpha in self._trails[i][:-1]:
                a = alpha * 0.40
                cr.set_source_rgba(rr, gg, bb, a)
                cr.arc(x, yt, DOT_R * alpha, 0, 2 * math.pi); cr.fill()
                cr.arc(x, yb, DOT_R * alpha, 0, 2 * math.pi); cr.fill()

            # leading dot — bright with glow
            if lv > 0.04:
                # outer glow
                cr.set_source_rgba(rr, gg, bb, 0.20)
                cr.arc(x, dot_y_top, DOT_R * 2.2, 0, 2 * math.pi); cr.fill()
                cr.arc(x, dot_y_bot, DOT_R * 2.2, 0, 2 * math.pi); cr.fill()
                # core dot
                cr.set_source_rgba(rr+(1-rr)*.5, gg+(1-gg)*.5, bb+(1-bb)*.5, 0.96)
                cr.arc(x, dot_y_top, DOT_R, 0, 2 * math.pi); cr.fill()
                cr.arc(x, dot_y_bot, DOT_R, 0, 2 * math.pi); cr.fill()

    def _draw_sparks(self, cr):
        self._update_sparks()
        for s in self._sparks:
            alpha = s[4] * 0.90
            cr.set_source_rgba(s[5], s[6], s[7], alpha)
            cr.arc(s[0], s[1], 1.5, 0, 2 * math.pi)
            cr.fill()

    def _draw_spinner(self, cr, h):
        t  = self._theme
        br, bg_, bb = t["border"]
        cx, cy = 26, h // 2
        r  = 11
        a  = self._pulse * 0.22
        sp = math.pi * 0.72

        cr.set_source_rgba(1, 1, 1, 0.07)
        cr.set_line_width(2.5)
        cr.arc(cx, cy, r, 0, 2 * math.pi); cr.stroke()

        cr.set_source_rgba(br, bg_, bb, 0.95)
        cr.set_line_width(2.5)
        cr.arc(cx, cy, r, a, a + sp); cr.stroke()

        dx = cx + r * math.cos(a + sp)
        dy = cy + r * math.sin(a + sp)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.90)
        cr.arc(dx, dy, 2.8, 0, 2 * math.pi); cr.fill()
