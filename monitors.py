# -*- coding: utf-8 -*-
"""Gestione monitor (risoluzione nativa) e DPI awareness su Windows."""

import ctypes
import ctypes.wintypes as wt
import os

_user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None


def make_dpi_aware():
    """Necessario per ottenere i pixel fisici (risoluzione massima) del monitor."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PER_MONITOR_AWARE_V2
        return
    except Exception:
        pass
    try:
        _user32.SetProcessDPIAware()
    except Exception:
        pass


def suppress_crash_dialogs():
    """Nessuna finestra di errore/Debugger JIT: in caso di crash il processo esce subito."""
    try:
        SEM_FAILCRITICALERRORS = 0x1
        SEM_NOGPFAULTERRORBOX = 0x2
        SEM_NOOPENFILEERRORBOX = 0x8000
        ctypes.windll.kernel32.SetErrorMode(
            SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX)
    except Exception:
        pass


def list_monitors():
    """Restituisce [(x, y, w, h), ...] in pixel fisici; il primario e' il primo (0,0)."""
    if _user32 is None:
        return []
    monitors = []
    try:
        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_int, wt.HMONITOR, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)

        def cb(hmon, hdc, lprect, lparam):
            r = lprect.contents
            monitors.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
            return 1

        _user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(cb), 0)
    except Exception:
        return []
    if monitors:
        monitors.sort(key=lambda m: 0 if (m[0] == 0 and m[1] == 0) else 1)
    return monitors


def primary_monitor():
    mons = list_monitors()
    if mons:
        return mons[0]
    try:
        import pygame
        sizes = pygame.display.get_desktop_sizes()
        if sizes:
            return (0, 0, sizes[0][0], sizes[0][1])
    except Exception:
        pass
    return (0, 0, 1920, 1080)


def monitor_at(x, y):
    """Monitor che contiene il punto (x, y); fallback: quello che lo interseca di piu'."""
    mons = list_monitors() or [primary_monitor()]
    for m in mons:
        if m[0] <= x < m[0] + m[2] and m[1] <= y < m[1] + m[3]:
            return m
    best, best_area = mons[0], -1
    for m in mons:
        ox = max(0, min(x, m[0] + m[2]) - max(x, m[0]))
        oy = max(0, min(y, m[1] + m[3]) - max(y, m[1]))
        area = ox * oy
        if area > best_area:
            best, best_area = m, area
    return best


def monitor_under_cursor():
    try:
        p = wt.POINT()
        _user32.GetCursorPos(ctypes.byref(p))
        return monitor_at(p.x, p.y)
    except Exception:
        return primary_monitor()


def set_window_position(x, y):
    """Sposta la finestra SDL corrente tramite variabile d'ambiente SDL (prima dell'apertura)."""
    os.environ["SDL_VIDEO_WINDOW_POS"] = "%d,%d" % (int(x), int(y))


def get_window_position():
    return None


def monitor_of_window():
    """Monitor su cui lavora l'utente (posizione del cursore)."""
    return monitor_under_cursor()
