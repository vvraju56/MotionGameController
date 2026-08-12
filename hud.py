import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

_FONT_DIR = os.environ.get("WINDIR", r"C:\Windows")
_MONO = ["CascadiaMono.ttf", "consola.ttf", "cour.ttf", "arial.ttf"]
_EMOJI = ["seguiemj.ttf", "seguisym.ttf"]

_cache = {}

_WHITE = (235, 235, 235, 255)
_GRAY = (165, 165, 165, 255)
_DIM = (105, 105, 110, 255)
_CYAN = (80, 220, 220, 255)
_GREEN = (96, 205, 130, 255)
_ORANGE = (250, 190, 80, 255)
_RED = (240, 90, 90, 255)


def _load(names, size):
    key = (tuple(names), size)
    if key in _cache:
        return _cache[key]
    font = None
    for name in names:
        path = os.path.join(_FONT_DIR, "Fonts", name)
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                break
            except Exception:
                font = None
    _cache[key] = font
    return font


def _mono(size):
    return _load(_MONO, size)


def _emoji(size):
    return _load(_EMOJI, size)


def _has_glyph(font, ch):
    if font is None:
        return False
    try:
        b = font.getbbox(ch)
        return b[2] - b[0] > 0 and b[3] - b[1] > 0
    except Exception:
        return False


def _box(draw, xy):
    try:
        draw.rounded_rectangle(xy, radius=7, fill=(10, 12, 18, 178))
    except AttributeError:
        draw.rectangle(xy, fill=(10, 12, 18, 190))


def render_status(draw, size, st):
    mono = _mono(13)
    title_font = _mono(15)
    x0, y0 = size[0] - 318, 12
    x1 = size[0] - 12
    keys = st.get("keys", {})
    key_rows = [
        ("SHIFT + W", _GREEN if keys.get("w") else _GRAY),
        ("CTRL", _GREEN if keys.get("ctrl") else _GRAY),
        ("SPACE", _GREEN if keys.get("space") else _GRAY),
    ]
    bottom_keys = key_rows
    action = st.get("action") or "idle"
    a_text = {"run": "RUNNING", "walk": "WALKING"}.get(action, "IDLE")
    a_color = {"run": _ORANGE, "walk": _GREEN}.get(action, _GRAY)
    mouse_on = keys.get("mouse", False)
    rows = [
        ("Camera", "ON", _GREEN if st.get("camera", True) else _RED, "OFF"),
        ("Tracking", "ACTIVE", _GREEN if st.get("tracking", False) else _RED, "LOST"),
        ("LEFT HAND", "RAISED", _GREEN if st.get("left_hand", False) else _GRAY, "LOWERED"),
        ("ACTION", a_text, a_color, "IDLE"),
        ("MOUSE", st.get("direction", "ACTIVE"), _GREEN if mouse_on else _GRAY, "IDLE"),
    ]
    height = 42 + len(rows) * 22 + 32 + len(bottom_keys) * 20 + 14
    y1 = y0 + height
    _box(draw, (x0, y0, x1, y1))

    title = "MOTION GAME CONTROL"
    tw = draw.textlength(title, font=title_font)
    draw.text((x0 + (x1 - x0 - tw) / 2, y0 + 7), title, font=title_font, fill=_CYAN)
    draw.line((x0 + 8, y0 + 31, x1 - 8, y0 + 31), fill=_DIM, width=1)

    y = y0 + 42

    for label, on_text, on_color, off_text in rows:
        value = on_text if on_color != _GRAY else off_text
        draw.text((x0 + 12, y), label, font=mono, fill=_WHITE)
        vx = x1 - 12 - draw.textlength(value, font=mono)
        draw.ellipse((vx - 16, y + 5, vx - 6, y + 15), fill=on_color)
        draw.text((vx, y), value, font=mono, fill=on_color if on_color != _GRAY else _GRAY)
        y += 22

    draw.line((x0 + 8, y, x1 - 8, y), fill=_DIM, width=1)
    y += 12
    draw.text((x0 + 12, y), "GAME INPUT", font=title_font, fill=_CYAN)
    y += 20

    for label, color in bottom_keys:
        draw.text((x0 + 12, y), label, font=mono, fill=_WHITE)
        value = "PRESSED" if color == _GREEN else "RELEASED"
        vx = x1 - 12 - draw.textlength(value, font=mono)
        draw.ellipse((vx - 16, y + 5, vx - 6, y + 15), fill=color)
        draw.text((vx, y), value, font=mono, fill=color if color == _GREEN else _GRAY)
        y += 20


_GUIDE = [
    ("\U0001F44B", "LEFT HAND UP", "Enable movement", _GREEN),
    ("\U0001F6B6", "Move normally", "W  (WALK)", _GREEN),
    ("\U0001F3C3", "Move / run faster", "SHIFT+W  (RUN)", _ORANGE),
    ("\U0001FA91", "Sit down", "CTRL", _GREEN),
    ("\U0001F998", "Jump", "SPACE", _GREEN),
    ("\U0001F44B", "Lower left hand", "Stop movement", _RED),
    ("\U0001F91A", "Right hand off center", "MOUSE", _GREEN),
]

_GUIDE_BODY = [
    ("LEFT HAND UP", "Enable movement", _GREEN),
    ("Move normally", "W  (WALK)", _GREEN),
    ("Move / run faster", "SHIFT+W  (RUN)", _ORANGE),
    ("Sit down", "CTRL", _GREEN),
    ("Jump", "SPACE", _GREEN),
    ("Lower left hand", "Stop movement", _RED),
    ("Right hand off center", "MOUSE", _GREEN),
]


def render_guide(draw, size):
    mono = _mono(13)
    title_font = _mono(15)
    w, h = size
    x0, x1 = 12, 300
    emoji_font = _emoji(16)
    use_emoji = all(_has_glyph(emoji_font, g) for g, _, _, _ in _GUIDE)

    lines = _GUIDE if use_emoji else [("", t, d, c) for t, d, c in _GUIDE_BODY]
    height = 42 + len(lines) * 23 + 12
    y1 = h - 12
    y0 = y1 - height
    _box(draw, (x0, y0, x1, y1))

    title = "HOW TO CONTROL"
    tw = draw.textlength(title, font=title_font)
    draw.text((x0 + (x1 - x0 - tw) / 2, y0 + 7), title, font=title_font, fill=_CYAN)
    draw.line((x0 + 8, y0 + 31, x1 - 8, y0 + 31), fill=_DIM, width=1)

    y = y0 + 42
    for glyph, label, result, color in lines:
        xt = x0 + 12
        if use_emoji:
            draw.text((xt, y - 2), glyph, font=emoji_font, fill=_WHITE)
            xt += max(draw.textlength(glyph, font=emoji_font), 20) + 6
        draw.text((xt, y), label, font=mono, fill=_WHITE)
        rw = draw.textlength(result, font=mono)
        draw.text((x1 - 12 - rw, y), result, font=mono, fill=color)
        y += 23


def render_test(draw, size, st):
    mono = _mono(13)
    title_font = _mono(15)
    x0, y0 = size[0] - 318, 12
    x1 = size[0] - 12
    keys = st.get("keys", {})
    camera_on = st.get("camera", True)
    tracking = st.get("tracking", False)
    hand_up = st.get("left_hand", False)
    action = st.get("action") or "idle"

    if keys.get("space"):
        current, cur_color = "JUMP", _ORANGE
    elif keys.get("ctrl"):
        current, cur_color = "SITTING", _GREEN
    elif action == "run":
        current, cur_color = "RUN", _ORANGE
    elif action == "walk":
        current, cur_color = "WALK", _GREEN
    else:
        current, cur_color = "IDLE", _GRAY

    key_rows = [
        ("W", _GREEN if keys.get("w") else _GRAY),
        ("SHIFT", _GREEN if keys.get("shift") else _GRAY),
        ("CTRL", _GREEN if keys.get("ctrl") else _GRAY),
        ("SPACE", _GREEN if keys.get("space") else _GRAY),
    ]
    height = 42 + 4 * 22 + 34 + 4 * 20 + 2 * 24 + 22 + 32 + len(key_rows) * 20 + 14
    y1 = y0 + height
    _box(draw, (x0, y0, x1, y1))

    title = "MOTION TEST MODE"
    tw = draw.textlength(title, font=title_font)
    draw.text((x0 + (x1 - x0 - tw) / 2, y0 + 7), title, font=title_font, fill=_CYAN)
    draw.line((x0 + 8, y0 + 31, x1 - 8, y0 + 31), fill=_DIM, width=1)

    def row(label, active, on_text, off_text, color):
        nonlocal y
        draw.text((x0 + 12, y), label, font=mono, fill=_WHITE)
        value = on_text if active else off_text
        vx = x1 - 12 - draw.textlength(value, font=mono)
        draw.ellipse((vx - 16, y + 5, vx - 6, y + 15), fill=color if active else _GRAY)
        draw.text((vx, y), value, font=mono, fill=color if active else _GRAY)
        y += 22

    y = y0 + 42

    def row(label, active, on_text, off_text, color):
        nonlocal y
        draw.text((x0 + 12, y), label, font=mono, fill=_WHITE)
        value = on_text if active else off_text
        vx = x1 - 12 - draw.textlength(value, font=mono)
        draw.ellipse((vx - 16, y + 5, vx - 6, y + 15), fill=color if active else _GRAY)
        draw.text((vx, y), value, font=mono, fill=color if active else _GRAY)
        y += 22

    def textrow(label, value, color=_WHITE):
        nonlocal y
        draw.text((x0 + 12, y), label, font=mono, fill=_WHITE)
        vx = x1 - 12 - draw.textlength(value, font=mono)
        draw.text((vx, y), value, font=mono, fill=color)
        y += 20

    def sliderrow(label, value, vmin=1, vmax=200):
        nonlocal y
        draw.text((x0 + 12, y), label, font=mono, fill=_WHITE)
        bx0 = x0 + 90
        bx1 = bx0 + 110
        t = max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
        draw.line((bx0, y + 8, bx1, y + 8), fill=_DIM, width=4)
        draw.line((bx0, y + 8, bx0 + int(t * 110), y + 8), fill=_CYAN, width=4)
        mx = bx0 + int(t * 110)
        draw.ellipse((mx - 5, y + 3, mx + 5, y + 13), fill=_ORANGE)
        draw.text((x1 - 12 - draw.textlength(str(value), font=mono), y), str(value), font=mono, fill=_ORANGE)
        y += 24

    y = y0 + 42
    row("Camera", camera_on, "ON", "OFF", _GREEN)
    row("Tracking", tracking, "ACTIVE", "LOST", _GREEN)
    row("Left Hand", hand_up, "RAISED", "LOWERED", _GREEN)
    row("Current", current != "IDLE", current, "IDLE", cur_color)

    draw.line((x0 + 8, y, x1 - 8, y), fill=_DIM, width=1)
    y += 12
    draw.text((x0 + 12, y), "RIGHT HAND", font=title_font, fill=_CYAN)
    y += 22
    wx, wy = st.get("wrist", (0.0, 0.0))
    dx, dy = st.get("delta", (0.0, 0.0))
    textrow("RIGHT X", f"{wx:.2f}")
    textrow("RIGHT Y", f"{wy:.2f}")
    textrow("DX (px)", f"{dx:+.0f}")
    textrow("DY (px)", f"{dy:+.0f}")
    sliderrow("SENS X", st.get("sensitivity", 35))
    sliderrow("SENS Y", st.get("sensitivity_y", 30))
    row("Direction", keys.get("mouse", False), st.get("direction", "CENTER"), "CENTER", _GREEN)

    draw.line((x0 + 8, y, x1 - 8, y), fill=_DIM, width=1)
    y += 12
    draw.text((x0 + 12, y), "KEYS", font=title_font, fill=_CYAN)
    y += 20
    for label, color in key_rows:
        draw.text((x0 + 12, y), label, font=mono, fill=_WHITE)
        value = "DOWN" if color == _GREEN else "UP"
        vx = x1 - 12 - draw.textlength(value, font=mono)
        draw.ellipse((vx - 16, y + 5, vx - 6, y + 15), fill=color)
        draw.text((vx, y), value, font=mono, fill=color if color == _GREEN else _GRAY)
        y += 20


def overlay_hud(bgr_frame, state, test_mode=False):
    rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(rgb).convert("RGBA")
    draw = ImageDraw.Draw(img)
    if test_mode:
        render_test(draw, img.size, state)
    else:
        render_status(draw, img.size, state)
    render_guide(draw, img.size)
    return cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)