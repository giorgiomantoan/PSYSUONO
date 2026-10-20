# -*- coding: utf-8 -*-
"""Genera una traccia di test 14 s con contenuto che varia (bassi/medi/alti)."""
import numpy as np
import wave

SR = 44100
DUR = 14.0
t = np.arange(int(SR * DUR)) / SR

# bomba di bassi + tappeto medio + arpello acuto, con envelope alternati
bass = 0.55 * np.sin(2 * np.pi * 55 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 1.5 * t)) ** 3
mid = 0.30 * np.sin(2 * np.pi * 440 * t) * (0.4 + 0.6 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.7 * t + 1.0)))
hi = 0.18 * np.sin(2 * np.pi * 3000 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 4.0 * t)) ** 2
kick_env = (0.5 + 0.5 * np.sin(2 * np.pi * 2.0 * t)) ** 6
bass += 0.5 * kick_env * np.sin(2 * np.pi * 70 * t)

mix = np.tanh((bass + mid + hi) * 1.2)
pcm = (mix * 32000).astype(np.int16)

with wave.open("test_track.wav", "wb") as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(SR)
    f.writeframes(pcm.tobytes())

print("scritto test_track.wav", len(pcm) / SR, "s")
