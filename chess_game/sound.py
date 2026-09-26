"""Tiny synthesized sound effects - no asset files, no numpy.

We build 16-bit mono PCM buffers by hand and hand them to pygame.mixer. If the
mixer can't be initialised (e.g. no audio device) everything degrades to no-ops.
"""

import array
import math

_RATE = 22050
_sounds = {}
_enabled = False
_user_enabled = True


def _tone(freqs, ms, volume=0.35, decay=True):
    n = int(_RATE * ms / 1000)
    buf = array.array("h", bytes(2 * n))
    for i in range(n):
        t = i / _RATE
        s = sum(math.sin(2 * math.pi * f * t) for f in freqs) / len(freqs)
        env = (1 - i / n) if decay else 1.0
        buf[i] = int(max(-1.0, min(1.0, s * env * volume)) * 32767)
    return buf


def init():
    global _enabled
    try:
        import pygame
        import pygame.mixer  # not present in every pygame build
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=_RATE, size=-16, channels=1)
        specs = {
            "move": ([330], 60),
            "capture": ([160, 90], 90),
            "castle": ([300, 450], 110),
            "check": ([660, 880], 140),
            "end": ([440, 330, 220], 300),
            "click": ([520], 35),
        }
        for name, (freqs, ms) in specs.items():
            _sounds[name] = pygame.mixer.Sound(buffer=_tone(freqs, ms).tobytes())
        _enabled = True
    except Exception:
        _enabled = False


def play(name):
    if _enabled and _user_enabled and name in _sounds:
        try:
            _sounds[name].play()
        except Exception:
            pass


def set_enabled(enabled):
    """Apply the user's sound preference without requiring an audio device."""

    global _user_enabled
    _user_enabled = bool(enabled)


def is_enabled():
    """Return the persisted user preference, independent of mixer availability."""

    return _user_enabled
