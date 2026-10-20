# -*- coding: utf-8 -*-
"""
PSYSUONO - tunnel kaleidoscopico infinito reattivo alla musica.

Avvio:
    py main.py                  -> schermo intero (risoluzione nativa del monitor)
    py main.py --windowed       -> finestra 1280x720
    py main.py "percorso.mp3"   -> apre subito il file

Controlli:
    SPAZIO      pausa/riprendi          F       full screen / finestra
    O           apri file audio         H       aiuto on/off
    < / >       indietro/avanti 10 s    TAB     HUD on/off
    + / -       volume                  S       salva screenshot
    [ / ]       velocita' tunnel -/+    ESC     esci
    Trascina un file audio sulla finestra per caricarlo.
"""

import argparse
import os
import random
import sys
import time

import numpy as np
import pygame

import audio
import monitors
import render


# --------------------------------------------------------------------------- #
#  Utilita'
# --------------------------------------------------------------------------- #
def parse_args():
    p = argparse.ArgumentParser(description="Tunnel audio-visivo kaleidoscopico")
    p.add_argument("file", nargs="?", default=None, help="file audio da riprodurre")
    p.add_argument("--windowed", action="store_true", help="avvia in finestra (default: full screen)")
    p.add_argument("--monitor", type=int, default=None, help="indice monitor (default: quello sotto il cursore)")
    p.add_argument("--speed", type=float, default=1.0, help="moltiplicatore di velocita' del tunnel")
    p.add_argument("--smoke", type=int, default=0, metavar="N",
                   help="modalita' test: renderizza N frame, salva lo screenshot ed esci")
    p.add_argument("--shot", default="smoke.png", help="percorso screenshot per --smoke")
    return p.parse_args()


def ask_audio_file():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title="Scegli un file audio",
            filetypes=[("Audio", "*.mp3 *.wav *.ogg *.flac *.m4a *.aac *.wma"),
                       ("Tutti i file", "*.*")])
        root.destroy()
        return path or None
    except Exception as exc:
        print("Dialogo file non disponibile (%s): trascina il file sulla finestra." % exc)
        return None


def ema(prev, target, attack, release, dt):
    """Smorzamento con attacco/ritmo diverso (normalizzato a 60 fps)."""
    rate = attack if target > prev else release
    alpha = 1.0 - (1.0 - rate) ** max(dt * 60.0, 0.0)
    return prev + (target - prev) * alpha


class Smooth:
    def __init__(self):
        self.v = np.zeros(audio.N_FEAT, dtype=np.float32)
        self.pulse = 0.0
        self.env = 0.0

    def update(self, raw, dt):
        atk, rel = 0.45, 0.14
        for i in range(audio.N_FEAT):
            self.v[i] = ema(float(self.v[i]), float(raw[i]), atk, rel, dt)
        bass = float(self.v[audio.FEAT_BASS])
        self.env = ema(self.env, bass, 0.35, 0.05, dt)
        transient = max(0.0, bass - self.env) * 5.0
        self.pulse = max(self.pulse * (0.86 ** (dt * 60.0)), min(transient, 1.0))
        return self.v


def idle_features(t):
    """Animazione morbida quando nessuna traccia e' caricata."""
    f = np.zeros(audio.N_FEAT, dtype=np.float32)
    f[audio.FEAT_BASS] = 0.22 + 0.14 * (0.5 + 0.5 * np.sin(t * 0.70))
    f[audio.FEAT_LOWMID] = 0.20 + 0.12 * (0.5 + 0.5 * np.sin(t * 0.53 + 1.2))
    f[audio.FEAT_MID] = 0.18 + 0.12 * (0.5 + 0.5 * np.sin(t * 0.41 + 2.4))
    f[audio.FEAT_HIGH] = 0.15 + 0.10 * (0.5 + 0.5 * np.sin(t * 0.63 + 3.1))
    f[audio.FEAT_AIR] = 0.12 + 0.08 * (0.5 + 0.5 * np.sin(t * 0.87 + 0.6))
    f[audio.FEAT_RMS] = 0.20 + 0.10 * (0.5 + 0.5 * np.sin(t * 0.47 + 1.9))
    f[audio.FEAT_CENTROID] = 0.35 + 0.15 * (0.5 + 0.5 * np.sin(t * 0.30))
    return f


K_SET = (7, 8, 9, 10, 12, 14, 16)   # simmetrie possibili del kaleidoscopio


class Shape:
    """Parametri geometrici del tunnel pilotati dal suono.

    La forma cambia con la musica:
      - simmetria (K): salta a un nuovo valore sui colpi di basso
      - densita' anelli: cresce con i bassi
      - larghezza petali: cresce con l'energia
      - morfatura ornamenti: segue le medie
      - torsione a spirale: medie + colpi
      - incastro mandala annidata: centroide/squilli degli alti
    """

    def __init__(self):
        self.sym = 10.0
        self.ring_scale = 1.0
        self.petal_w = 0.5
        self.morph = 0.2
        self.twist = 0.06
        self.nest = 0.5
        self._last_sym_change = -10.0

    def update(self, bass, mid, treble, energy, centroid, pulse, dt, elapsed):
        self.ring_scale = ema(self.ring_scale, float(np.clip(0.75 + 0.85 * bass, 0.55, 1.80)),
                              0.30, 0.10, dt)
        self.petal_w = ema(self.petal_w, float(np.clip(0.25 + 0.95 * energy + 0.35 * pulse, 0.0, 1.0)),
                           0.30, 0.12, dt)
        self.morph = ema(self.morph, float(np.clip(0.60 * mid + 0.65 * pulse, 0.0, 1.0)),
                         0.35, 0.12, dt)
        self.twist = ema(self.twist, float(np.clip(0.05 + 0.55 * mid + 0.40 * pulse, 0.0, 1.10)),
                         0.25, 0.10, dt)
        self.nest = ema(self.nest, float(np.clip(0.35 + 1.20 * (centroid - 0.25) + 0.30 * pulse,
                                                 0.0, 1.0)), 0.25, 0.10, dt)
        # la simmetria cambia solo su colpi netti, con un minimo di intervallo
        if pulse > 0.42 and (elapsed - self._last_sym_change) > 0.45:
            choices = [k for k in K_SET if k != int(self.sym)]
            self.sym = float(random.choice(choices))
            self._last_sym_change = elapsed
        return self


# --------------------------------------------------------------------------- #
#  Finestra / full screen
# --------------------------------------------------------------------------- #
class Window:
    """Gestione finestra / schermo intero.

    Nota: con il flag OPENGL pygame non ridimensiona la finestra esistente
    (set_mode restituiva sempre la prima dimensione), quindi il cambio di
    modalita' avviene ricreando il contesto video con pygame.display.quit().
    Il contesto OpenGL va quindi ricreato (vedi main) dopo ogni cambio.
    """

    def __init__(self, fullscreen, monitor_index=None):
        mons = monitors.list_monitors() or [monitors.primary_monitor()]
        if monitor_index is not None and 0 <= monitor_index < len(mons):
            self.monitor = mons[monitor_index]
        else:
            self.monitor = monitors.monitor_under_cursor()
        self.fullscreen = bool(fullscreen)
        self.surface = None
        self._open()

    def _open(self):
        if self.fullscreen:
            x, y, w, h = self.monitor
            # SDL posiziona la finestra sul monitor scelto: il display in
            # full screen e' quello che la contiene
            monitors.set_window_position(x + 40, y + 40)
            flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.FULLSCREEN
        else:
            w, h = 1280, 720
            os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
            flags = pygame.OPENGL | pygame.DOUBLEBUF
        try:
            pygame.display.quit()          # libera contesto e finestra precedenti
        except Exception:
            pass
        self.surface = pygame.display.set_mode((w, h), flags, vsync=1)
        pygame.display.set_caption("PSYSUONO - tunnel kaleidoscopico reattivo alla musica")
        return self.size()

    def size(self):
        try:
            return pygame.display.get_window_size()
        except Exception:
            return pygame.display.get_surface().get_size()

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.monitor = monitors.monitor_under_cursor()
        return self._open()

    def current_monitor_size(self):
        return (self.monitor[2], self.monitor[3])


# --------------------------------------------------------------------------- #
#  Programma
# --------------------------------------------------------------------------- #
def main():
    args = parse_args()
    monitors.make_dpi_aware()
    monitors.suppress_crash_dialogs()

    pygame.init()
    try:
        pygame.mixer.init(44100, -16, 2, 1024)
        audio_ok = True
    except Exception as exc:
        audio_ok = False
        print("Mixer audio non inizializzato (%s): visualizzazione in sola analisi." % exc)

    win = Window(fullscreen=not args.windowed, monitor_index=args.monitor)
    w, h = win.size()

    renderer = render.Renderer(w, h)
    hud = render.Hud()

    # --- caricamento traccia ---
    player = audio.Player(audio_enabled=audio_ok)
    track = None
    path = args.file
    if path:
        try:
            track = audio.Track.load(path)
            player.load(track)
            print("Caricato: %s (%.1f s)" % (track.name, track.duration))
        except Exception as exc:
            print("Errore caricamento: %s" % exc)
            track = None

    smooth = Smooth()
    shape = Shape()
    show_hud = True
    help_visible = True
    speed_mult = float(np.clip(args.speed, 0.1, 5.0))

    travel = 0.0
    rot = 0.0
    hue_drift = 0.0
    glow = 0.0
    t_start = time.perf_counter()
    last = t_start
    fps = 60.0
    frame = 0
    running = True
    clock = pygame.time.Clock()
    msg = "Trascina un file audio qui (o premi O per sceglierlo)"

    while running:
        dt = clock.tick(120) / 1000.0
        dt = min(max(dt, 1e-4), 0.1)
        now = time.perf_counter()
        elapsed = now - t_start
        fps = fps * 0.92 + (1.0 / dt) * 0.08

        # ---------------------------- eventi ---------------------------- #
        if args.smoke:
            # inietta una sequenza di tasti per collaudare tutti i controlli
            key_seq = {15: pygame.K_SPACE, 25: pygame.K_RIGHT, 35: pygame.K_SPACE,
                       45: pygame.K_UP, 55: pygame.K_EQUALS, 65: pygame.K_h,
                       75: pygame.K_TAB, 85: pygame.K_TAB, 95: pygame.K_MINUS,
                       105: pygame.K_LEFT}
            if frame in key_seq:
                pygame.event.post(pygame.event.Event(
                    pygame.KEYDOWN, key=key_seq[frame], mod=0, unicode="", scancode=0))
            if frame in (args.smoke - 8, args.smoke - 4):
                pygame.event.post(pygame.event.Event(
                    pygame.KEYDOWN, key=pygame.K_f, mod=0, unicode="", scancode=0))

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.DROPFILE:
                try:
                    track = audio.Track.load(ev.file)
                    player.load(track)
                    msg = "Caricato: %s" % track.name
                    print(msg)
                except Exception as exc:
                    msg = "Errore: %s" % exc
                    print(msg)
            elif ev.type == pygame.KEYDOWN:
                k = ev.key
                if k in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif k == pygame.K_SPACE:
                    player.toggle_pause()
                elif k == pygame.K_f:
                    w, h = win.toggle_fullscreen()
                    # il contesto OpenGL e' stato ricreato: nuove risorse GL
                    renderer = render.Renderer(w, h)
                    hud = render.Hud()
                elif k == pygame.K_o:
                    p = ask_audio_file()
                    if p:
                        try:
                            track = audio.Track.load(p)
                            player.load(track)
                            msg = "Caricato: %s" % track.name
                            print(msg)
                        except Exception as exc:
                            msg = "Errore: %s" % exc
                            print(msg)
                elif k in (pygame.K_LEFT, pygame.K_COMMA):
                    player.seek_rel(-10.0)
                elif k in (pygame.K_RIGHT, pygame.K_PERIOD):
                    player.seek_rel(10.0)
                elif k == pygame.K_UP:
                    player.set_volume(player.volume + 0.05)
                elif k == pygame.K_DOWN:
                    player.set_volume(player.volume - 0.05)
                elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    speed_mult = min(4.0, speed_mult * 1.15)
                elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    speed_mult = max(0.2, speed_mult / 1.15)
                elif k == pygame.K_r:
                    speed_mult = 1.0
                elif k == pygame.K_h:
                    help_visible = not help_visible
                elif k == pygame.K_TAB:
                    show_hud = not show_hud
                elif k == pygame.K_s:
                    out = os.path.join(os.getcwd(), "tunnel_%s.png" % time.strftime("%H%M%S"))
                    try:
                        render.save_screenshot(out)
                        print("Screenshot: %s" % out)
                    except Exception as exc:
                        print("Screenshot non riuscito: %s" % exc)
            elif ev.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED):
                w, h = win.size()
                renderer.resize(w, h)

        # ------------------------- stato audio -------------------------- #
        if track is not None and player.is_paused():
            raw = track.features_at(player.position())
        elif track is not None:
            raw = track.features_at(player.position())
        else:
            raw = idle_features(elapsed)

        sm = smooth.update(raw, dt)
        bass = float(sm[audio.FEAT_BASS])
        mid = float(sm[audio.FEAT_MID])
        treble = float(np.maximum(sm[audio.FEAT_HIGH], sm[audio.FEAT_AIR]))
        energy = float(sm[audio.FEAT_RMS])
        centroid = float(sm[audio.FEAT_CENTROID])
        pulse = smooth.pulse

        # --- velocita' del tunnel: cambia con il contenuto sonoro ---
        speed = speed_mult * (0.55 + 2.6 * bass + 1.5 * energy + 1.1 * pulse)
        travel += speed * dt

        # --- rotazione: dipende dalle medie ---
        rot += (0.05 + 0.35 * mid + 0.25 * pulse) * dt

        # --- colore: deriva dallo spettro ---
        hue_drift += 0.020 * dt
        hue = (hue_drift
               + 0.55 * bass
               + 0.30 * mid
               + 0.35 * centroid
               + 0.25 * treble) % 1.0
        glow = ema(glow, 0.35 * energy + 0.65 * pulse, 0.5, 0.08, dt)

        # --- forma: geometria che cambia con la musica ---
        shape.update(bass, mid, treble, energy, centroid, pulse, dt, elapsed)

        # --------------------------- disegno ---------------------------- #
        state = dict(time=elapsed, travel=travel, bass=bass, mid=mid, treble=treble,
                     energy=energy, centroid=centroid, hue=hue, rot=rot,
                     pulse=pulse, glow=glow,
                     sym=shape.sym, ring_scale=shape.ring_scale, petal_w=shape.petal_w,
                     morph=shape.morph, twist=shape.twist, nest=shape.nest)
        renderer.draw(state)

        if show_hud:
            lines = []
            if track is not None:
                lines.append("%s   %s / %s   vol %d%%   tunnel x%.2f   sim %d"
                             % (track.name, audio.fmt_time(player.position()),
                                audio.fmt_time(track.duration), int(player.volume * 100),
                                speed_mult, int(shape.sym)))
            else:
                lines.append("PSYSUONO   nessuna traccia   tunnel x%.2f   sim %d"
                             % (speed_mult, int(shape.sym)))
            if help_visible:
                lines.append(msg)
                lines.append("SPAZIO pausa | F full screen | O apri file | < > seek 10s | + - volume")
                lines.append("[ ] velocita tunnel | S screenshot | TAB HUD | H aiuto | ESC esci")
            lines.append("%dx%d  %d FPS%s%s" % (w, h, int(round(fps)),
                                                "  |  PAUSA" if player.is_paused() else "",
                                                "  |  %s" % msg if track is None and not help_visible else ""))
            hud.set_lines(lines)
        else:
            hud.set_lines([])
        hud.draw(w, h)

        pygame.display.flip()
        frame += 1

        if args.smoke and frame >= args.smoke:
            out = args.shot
            render.save_screenshot(out)
            print("SMOKE OK  frame=%d  fps=%.1f  screenshot=%s" % (frame, fps, out))
            running = False

    print("chiusura...")
    try:
        pygame.quit()
    except Exception as exc:
        print("errore in pygame.quit():", exc)
    print("shutdown ok")


if __name__ == "__main__":
    _code = 0
    try:
        main()
        print("main tornato")
    except KeyboardInterrupt:
        _code = 0
    except Exception as exc:                       # mostra l'errore anche senza console
        _code = 1
        import traceback
        tb = traceback.format_exc()
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "error.log"), "a", encoding="utf-8") as fh:
                fh.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n" + tb + "\n")
        except Exception:
            pass
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, "%s\n\n%s" % (exc, tb[-1200:]), "PSYSUONO - errore", 0x10)
        except Exception:
            sys.stderr.write(tb)
    finally:
        # uscita immediata: evita l'access violation di SDL/OpenGL durante
        # la fase di shutdown dell'interprete (audio gia' fermato da pygame.quit)
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        os._exit(_code)
