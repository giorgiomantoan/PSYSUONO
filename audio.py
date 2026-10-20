# -*- coding: utf-8 -*-
"""Caricamento audio, riproduzione e analisi spettrale (FFT).

La traccia viene decodificata una volta in PCM mono: da esso si estraggono,
frame dopo frame (hop = 512 campioni ~ 11,6 ms), le bande che pilotano
colore, luminosita' e velocita' del tunnel.
"""

import os
import shutil
import subprocess
import time

import numpy as np
import pygame

SR = 44100          # frequenza di campionamento analisi
WIN = 2048          # finestra FFT (~46 ms)
HOP = 512           # passo frame (~11,6 ms)

# (nome, freq_bassa, freq_alta)
BANDS = (
    ("bass",     30,   140),
    ("lowmid",  140,   500),
    ("mid",     500,  2000),
    ("high",   2000,  6000),
    ("air",    6000, 14000),
)
N_FEAT = len(BANDS) + 2   # + rms + centroide spettrale
FEAT_BASS, FEAT_LOWMID, FEAT_MID, FEAT_HIGH, FEAT_AIR, FEAT_RMS, FEAT_CENTROID = range(N_FEAT)


# --------------------------------------------------------------------------- #
#  Decodifica
# --------------------------------------------------------------------------- #
def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    base = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(base, "ffmpeg.exe"), os.path.join(base, "bin", "ffmpeg.exe")):
        if os.path.isfile(cand):
            return cand
    return None


def decode_mono(path, sr=SR):
    """Decodifica l'intero file in mono float32 a `sr`. Solleva RuntimeError."""
    ff = find_ffmpeg()
    if ff:
        cmd = [ff, "-v", "error", "-i", path,
               "-ac", "1", "-ar", str(sr), "-f", "s16le", "-acodec", "pcm_s16le", "-"]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=300)
        except OSError as exc:
            raise RuntimeError("Impossibile avviare ffmpeg: %s" % exc)
        if proc.returncode != 0 or not proc.stdout:
            err = proc.stderr.decode("utf-8", "replace").strip()
            raise RuntimeError("ffmpeg non ha potuto decodificare il file:\n" + err)
        data = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        if data.size == 0:
            raise RuntimeError("Il file non contiene campioni audio decodificabili.")
        return data

    # Fallback: decodifica tramite SDL_mixer (serve il mixer gia' inizializzato)
    try:
        snd = pygame.mixer.Sound(path)
        arr = pygame.sndarray.array(snd)
    except Exception as exc:
        raise RuntimeError(
            "Nessun decodificatore disponibile (installa ffmpeg o verifica il file): %s" % exc)
    arr = np.asarray(arr, dtype=np.float32)
    if arr.ndim == 2:                       # stereo -> mono
        arr = arr.mean(axis=1)
    if arr.size and float(np.max(np.abs(arr))) > 1.5:   # ancora in scala intera
        arr = arr / float(np.iinfo(np.int16).max)
    if arr.size == 0:
        raise RuntimeError("Il file non contiene campioni audio decodificabili.")
    return arr


# --------------------------------------------------------------------------- #
#  Analisi spettrale
# --------------------------------------------------------------------------- #
def extract_features(samples, sr=SR):
    """Restituisce feat[N_FRAME, N_FEAT] float32 normalizzato in [0,1]."""
    if samples.size < WIN:
        samples = np.pad(samples, (0, WIN - samples.size))
    window = np.hanning(WIN).astype(np.float32)
    freqs = np.fft.rfftfreq(WIN, 1.0 / sr)
    masks = [((freqs >= lo) & (freqs < hi)) for _, lo, hi in BANDS]

    starts = np.arange(0, samples.size - WIN + 1, HOP)
    if starts.size == 0:
        starts = np.array([0])
    n = starts.size
    out = np.zeros((n, N_FEAT), dtype=np.float32)

    sw = np.lib.stride_tricks.sliding_window_view(samples, WIN)[::HOP]
    if sw.shape[0] > n:
        sw = sw[:n]

    chunk = 1024
    for i0 in range(0, n, chunk):
        block = sw[i0:i0 + chunk] * window          # (c, WIN) float32
        c = block.shape[0]
        mag = np.abs(np.fft.rfft(block, axis=1)).astype(np.float32)
        sub = out[i0:i0 + c]
        for b, mask in enumerate(masks):
            sub[:, b] = mag[:, mask].mean(axis=1)
        sub[:, FEAT_RMS] = np.sqrt(np.mean(block * block, axis=1))
        tot = mag.sum(axis=1) + 1e-9
        sub[:, FEAT_CENTROID] = (mag * freqs[None, :]).sum(axis=1) / tot / 6000.0
        del mag, block

    # normalizzazione robusta per traccia (percentile 96) + gamma per
    # rendere percepibili anche i passage tranquilli
    for b in range(N_FEAT):
        col = out[:, b]
        scale = float(np.percentile(col, 96))
        if scale < 1e-9:
            scale = float(col.max()) if col.max() > 1e-9 else 1.0
        out[:, b] = np.clip(col / scale, 0.0, 1.0)
    out[:, :FEAT_RMS] = np.power(out[:, :FEAT_RMS], 0.75)
    out[:, FEAT_RMS] = np.power(out[:, FEAT_RMS], 0.75)
    return out


class Track:
    def __init__(self, path, samples, feat, sr=SR, hop=HOP):
        self.path = path
        self.name = os.path.basename(path)
        self.samples = samples
        self.feat = feat
        self.sr = sr
        self.hop = hop
        self.duration = samples.size / float(sr)

    @classmethod
    def load(cls, path):
        if not os.path.isfile(path):
            raise RuntimeError("File inesistente: %s" % path)
        samples = decode_mono(path)
        feat = extract_features(samples)
        return cls(path, samples, feat)

    def features_at(self, t):
        """Frame interpolato alla posizione `t` (secondi)."""
        if self.feat is None or self.feat.shape[0] == 0:
            return np.zeros(N_FEAT, dtype=np.float32)
        f = (t * self.sr) / self.hop
        f = float(np.clip(f, 0.0, self.feat.shape[0] - 1))
        i0 = int(f)
        i1 = min(i0 + 1, self.feat.shape[0] - 1)
        a = f - i0
        return self.feat[i0] * (1.0 - a) + self.feat[i1] * a

    def filename(self):
        return self.path


# --------------------------------------------------------------------------- #
#  Riproduzione
# --------------------------------------------------------------------------- #
class Player:
    """Riproduzione con orologio proprio (pausa, seek, volume, loop)."""

    def __init__(self, audio_enabled=True):
        self.audio = audio_enabled
        self.duration = 0.0
        self.playing = False
        self._base = 0.0
        self._t0 = time.perf_counter()
        self._paused = False
        self._restart = False
        self.volume = 0.85

    # -- stato ---------------------------------------------------------------
    def position(self):
        if not self.playing:
            return 0.0
        raw = self._base
        if not self._paused:
            raw += time.perf_counter() - self._t0
        if self.duration > 0.0:
            return raw % self.duration
        return raw

    def is_paused(self):
        return self._paused

    # -- comandi -------------------------------------------------------------
    def load(self, track):
        self.duration = track.duration
        self._base = 0.0
        self._t0 = time.perf_counter()
        self._paused = False
        self._restart = False
        self.playing = True
        if self.audio:
            try:
                pygame.mixer.music.load(track.path)
                pygame.mixer.music.set_volume(self.volume)
                pygame.mixer.music.play(loops=-1)
            except Exception as exc:
                self.audio = False
                print("Riproduzione audio non disponibile (%s): il tunnel sara' guidato "
                      "solo dall'analisi della traccia." % exc)

    def pause(self):
        if not self.playing or self._paused:
            return
        self._base = self.position()
        self._paused = True
        if self.audio:
            try:
                pygame.mixer.music.pause()
            except Exception:
                pass

    def resume(self):
        if not self._paused:
            return
        self._paused = False
        self._t0 = time.perf_counter()
        if self.audio:
            try:
                if self._restart:
                    pygame.mixer.music.play(loops=-1, start=self._base % max(self.duration, 1e-6))
                    self._restart = False
                else:
                    pygame.mixer.music.unpause()
            except Exception:
                pass

    def toggle_pause(self):
        self.pause() if not self._paused else self.resume()

    def seek(self, t):
        if self.duration <= 0.0:
            return
        t = float(np.clip(t, 0.0, max(0.0, self.duration - 0.05)))
        self._base = t
        self._t0 = time.perf_counter()
        if not self.audio:
            return
        if self._paused:
            self._restart = True
            return
        try:
            pygame.mixer.music.set_pos(t)
        except Exception:
            try:
                pygame.mixer.music.play(loops=-1, start=t)
            except Exception:
                pass

    def seek_rel(self, dt):
        self.seek(self.position() + dt)

    def set_volume(self, v):
        self.volume = float(np.clip(v, 0.0, 1.0))
        if self.audio:
            try:
                pygame.mixer.music.set_volume(self.volume)
            except Exception:
                pass


def fmt_time(sec):
    sec = max(0, int(sec))
    return "%d:%02d" % (sec // 60, sec % 60)
