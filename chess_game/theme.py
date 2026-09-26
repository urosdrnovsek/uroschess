"""Read the active Omarchy colour theme and derive the palette the UI paints
with. Falls back to a Tokyo-Night-ish dark palette when Omarchy isn't present.

Omarchy writes the current theme's colours to
``~/.local/state/omarchy/current/theme/colors.toml`` (a flat ``key = "#hex"``
table: ``mode``, ``accent``, ``background``/``*_background``, ``foreground``/
``*_foreground``, ``muted``, ``selection``, ``red``/``green``/``yellow``/…).

Portable: no hard dependency on ``tomllib`` (3.11+) — the flat file is parsed by
hand when neither ``tomllib`` nor ``tomli`` is available. When Omarchy / Hyprland
aren't present everything falls back to a built-in dark palette.
"""

import json
import re
import subprocess
from pathlib import Path

try:                                    # stdlib on 3.11+, backport otherwise
    import tomllib as _toml
except ModuleNotFoundError:
    try:
        import tomli as _toml
    except ModuleNotFoundError:
        _toml = None

_CANDIDATES = (
    Path.home() / ".local/state/omarchy/current/theme/colors.toml",
    Path.home() / ".config/omarchy/current/theme/colors.toml",
)

_FALLBACK = {
    "mode": "dark",
    "accent": "#7aa2f7", "selection": "#292e42", "muted": "#414868",
    "background": "#1a1b26", "dark_background": "#13141c",
    "lighter_background": "#24283b",
    "foreground": "#a9b1d6", "dark_foreground": "#565f89",
    "bright_foreground": "#c0caf5",
    "red": "#f7768e", "yellow": "#e0af68", "green": "#9ece6a", "blue": "#7aa2f7",
}


def _hex(s):
    s = s.strip().lstrip("#")
    if len(s) == 3:                     # #abc -> #aabbcc
        s = "".join(ch * 2 for ch in s)
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        return (128, 128, 128)


def _clamp(v):
    return max(0, min(255, int(round(v))))


def _mix(a, b, t):
    return tuple(_clamp(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _lighten(c, n):
    return tuple(_clamp(c[i] + n) for i in range(3))


def _luma(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _colors_path():
    for p in _CANDIDATES:
        try:
            if p.is_file():
                return p
        except OSError:
            pass
    return None


def colors_mtime():
    p = _colors_path()
    try:
        return p.stat().st_mtime if p else None
    except OSError:
        return None


def theme_name():
    try:
        out = subprocess.run(["omarchy-theme-current"], capture_output=True,
                             text=True, timeout=1)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def hypr_rounding(default=10):
    """The compositor's window corner radius, so panels can match it."""
    try:
        out = subprocess.run(
            ["hyprctl", "getoption", "decoration:rounding", "-j"],
            capture_output=True, text=True, timeout=1).stdout
        d = json.loads(out)
        if d.get("set"):
            return max(0, int(d.get("int", default)))
    except Exception:
        pass
    return default


_FLAT_LINE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*=\s*"([^"]*)"\s*(?:#.*)?$')


def _parse_flat(text):
    """Omarchy's colors.toml is a flat `key = "value"` table — parse it without
    a TOML library so we don't need Python 3.11+."""
    out = {}
    for line in text.splitlines():
        m = _FLAT_LINE.match(line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def _load_raw():
    p = _colors_path()
    if p is None:
        return dict(_FALLBACK), False
    try:
        text = p.read_text()
    except OSError:
        return dict(_FALLBACK), False
    try:
        data = _toml.loads(text) if _toml is not None else _parse_flat(text)
    except Exception:
        data = _parse_flat(text)
    raw = dict(_FALLBACK)
    raw.update({k: v for k, v in data.items() if isinstance(v, str)})
    return raw, True


class Palette:
    """Every colour the UI needs, resolved from the active Omarchy theme."""

    def __init__(self):
        raw, self.from_omarchy = _load_raw()
        self.name = theme_name() or ("Omarchy" if self.from_omarchy else "Default")
        self.rounding = hypr_rounding()

        def g(k):
            return _hex(raw.get(k, _FALLBACK.get(k, "#808080")))

        self.mode = raw.get("mode", "dark")
        light = self.mode == "light"

        self.accent = g("accent")
        self.bg = g("background")
        self.bg_dim = g("dark_background")
        self.surface = g("lighter_background")
        self.text = g("foreground")
        self.text_dim = g("dark_foreground")
        self.sel_raw = g("selection")
        self.good, self.warn, self.bad = g("green"), g("yellow"), g("red")

        ink = (250, 250, 252) if not light else (255, 255, 255)
        self.panel = self.surface
        self.panel_line = _mix(self.surface, self.text, 0.30)
        self.btn = _mix(self.surface, self.text, 0.11)
        self.btn_hot = _mix(self.surface, self.accent, 0.24)
        self.btn_active = self.accent
        self.on_accent = (20, 18, 22) if _luma(self.accent) > 150 else (250, 250, 252)
        self.field = _mix(self.bg, self.text, 0.07)

        # board squares — force checker contrast while keeping the theme's tint
        if light:
            self.sq_light = _mix(self.surface, ink, 0.38)
            self.sq_dark = _mix(_mix(self.surface, self.text, 0.36),
                                self.accent, 0.10)
            self.frame = _mix(self.sq_dark, self.text, 0.42)
        else:
            self.sq_light = _mix(_mix(self.surface, self.text, 0.32),
                                 self.accent, 0.07)
            self.sq_dark = _mix(self.surface, self.bg_dim, 0.62)
            self.frame = _mix(self.bg_dim, self.sq_dark, 0.32)
        self.frame_hi = _lighten(self.frame, 24)
        self.coord = _mix(self.frame, self.text if light else ink, 0.9)

        # in-play square tints
        self.sel = _mix(self.sq_light, self.warn, 0.55)
        self.lastmove = _mix(self.sq_light, self.accent, 0.42)
        self.check = self.bad
        self.dot = (0, 0, 0, 70) if not light else (70, 55, 70, 80)

        self.menu_bg_top = _mix(self.bg, self.accent, 0.05)
        self.menu_bg_bot = self.bg_dim
