# -*- coding: utf-8 -*-
"""Genera l'icona PSYSUONO (mandala kaleidoscopica) -> icon.png / icon.ico"""
import numpy as np
import pygame
from PIL import Image

S = 512
y, x = np.mgrid[0:S, 0:S].astype(np.float64)
u = (x - S / 2) / (S / 2 - 4)
v = (y - S / 2) / (S / 2 - 4)

r = np.sqrt(u * u + v * v) + 1e-4
a = np.arctan2(v, u)

K = 10.0
seg = 2 * np.pi / K
af = np.abs((a + np.pi) % seg - seg / 2) / (seg / 2)     # 0 centro petalo, 1 bordo

depth = 1.0 / np.maximum(r, 0.04)
d = depth * 0.45
ring = d % 1.0
band = np.sin(ring * np.pi) ** 1.4
petal = (1.0 - np.minimum(af, 1.0)) ** 1.3
spokes = (0.5 + 0.5 * np.cos(af * np.pi * 6.0)) ** 2

inten = band * petal * (0.55 + 0.45 * spokes)
inten = np.clip(inten, 0, 1)
inten *= np.clip((r - 0.05) / 0.05, 0, 1)                # centro scuro
inten *= np.clip((1.35 - r) / 0.25, 0, 1)                # bordi morbidi

t = 0.60 * inten + 0.16 * ring + 0.06 * af + 0.02
phase = np.array([0.0, 0.33, 0.67])
col = 0.5 + 0.5 * np.cos(2 * np.pi * (t[..., None] + phase))
col = np.clip(col, 0, 1) ** 1.7
col *= (0.15 + 1.75 * inten)[..., None]

rgb = np.clip(col * 255, 0, 255).astype(np.uint8)
alpha = np.clip(col.max(axis=2) * 340, 0, 255).astype(np.uint8)
rgba = np.dstack([rgb, alpha])

pygame.init()
surf = pygame.image.fromstring(rgba.tobytes(), (S, S), "RGBA", False)
pygame.image.save(surf, "icon.png")

img = Image.open("icon.png").convert("RGBA")
img.save("icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                            (64, 64), (128, 128), (256, 256)])
print("create icon.png / icon.ico")
