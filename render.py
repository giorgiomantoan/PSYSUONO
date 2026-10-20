# -*- coding: utf-8 -*-
"""Renderer OpenGL: tunnel kaleidoscopico infinito generato da shader."""

import pygame
from OpenGL.GL import *  # noqa: F401,F403

VERTEX_SRC = """
#version 120
void main()
{
    gl_Position = vec4(gl_Vertex.xy, 0.0, 1.0);
}
"""

# Tunnel mandala: mappatura prospettica 1/r + simmetria kaleidoscopica.
# Parametri audio:
#   uTravel  -> avanzamento (velocita', pilotata dal basso/energia)
#   uHue     -> rotazione della palette (colore guidato dallo spettro)
#   uPulse   -> inviluppo transitorio del basso (lampi)
FRAGMENT_SRC = """
#version 120

uniform vec2  uRes;
uniform float uTime;
uniform float uTravel;   // distanza percorsa dentro il tunnel (audio -> velocita')
uniform float uBass;
uniform float uMid;
uniform float uTreble;
uniform float uEnergy;
uniform float uCentroid;
uniform float uHue;      // offset della palette (colore -> suono)
uniform float uRot;
uniform float uPulse;
uniform float uGlow;
// --- forma guidata dalla musica ---
uniform float uSym;      // simmetria del kaleidoscopio (cambia sui colpi di basso)
uniform float uRingScale;// densita' degli anelli (bassi)
uniform float uPetalW;   // larghezza dei petali (energia)
uniform float uMorph;    // morfatura degli ornamenti (medi)
uniform float uTwist;    // torsione a spirale (medi + colpi)
uniform float uNest;     // incastro della mandala annidata (centroide/squilli)

const float PI  = 3.14159265;
const float TAU = 6.28318530;

float hash21(vec2 p)
{
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float vnoise(vec2 p)
{
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm4(vec2 p)
{
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) { v += a * vnoise(p); p = p * 2.03 + vec2(1.7, 9.2); a *= 0.5; }
    return v;
}

float fbm3(vec2 p)
{
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 3; i++) { v += a * vnoise(p); p = p * 2.11 + vec2(4.1, 2.7); a *= 0.5; }
    return v;
}

// palette psicchedelica stile mandala
vec3 palette(float t)
{
    vec3 c = vec3(0.5) + vec3(0.5) * cos(TAU * (t + vec3(0.00, 0.33, 0.67)));
    return c;
}

void main()
{
    vec2 uv = (gl_FragCoord.xy - 0.5 * uRes) / uRes.y;

    float cr = cos(uRot), sr = sin(uRot);
    uv = mat2(cr, -sr, sr, cr) * uv;

    float r   = length(uv) + 1e-5;
    float ang = atan(uv.y, uv.x);

    // ---- prospettiva del tunnel: 1/r = profondita' ----
    float depth = 1.0 / r;
    float d     = depth * 0.55 * uRingScale + uTravel;   // anelli piu' o meno fitti

    // ---- torsione a spirale (cambia con la musica) ----
    ang += uTwist * log(depth + 1.0);

    // ---- simmetria kaleidoscopica (mandala) ----
    float K    = uSym;
    float seg  = TAU / K;
    float a0   = mod(ang + PI, seg);
    float u    = abs(a0 - 0.5 * seg) / (0.5 * seg);          // 0 centro petalo, 1 bordo
    // seconda piega ad alta frequenza verso l'esterno (mandala annidata)
    float a1   = mod(ang + PI, seg * 0.5);
    float u2   = abs(a1 - seg * 0.25) / (seg * 0.25);
    u          = mix(u, u2, uNest * smoothstep(0.45, 0.92, r));

    // ---- maschere: anelli (con fughe nere) x petali ----
    float ring      = fract(d);
    float ringMask  = pow(clamp(sin(ring * PI), 0.0, 1.0), 1.25 + 0.60 * uBass);
    float edge      = mix(0.30, 0.78, uPetalW);              // larghezza petali -> audio
    float petalMask = 1.0 - smoothstep(edge, 0.98, u);
    petalMask = pow(petalMask, 1.40);

    float detailFade = smoothstep(0.015, 0.10, r);   // riduce l'aliasing verso il centro

    // ---- morfatura degli ornamenti (modulata dal suono) ----
    float uM = u + uMorph * 0.16 * sin(ring * TAU * 3.0 + ang * 4.0);

    // ---- ornamento frattale interno ----
    float n1 = fbm4(vec2(u * 6.0 + 0.12 * sin(uTime * 0.20), d * 4.0));
    float n2 = fbm3(vec2(u * 22.0 + 3.1, d * 14.0));
    float spokes = pow(0.5 + 0.5 * cos(uM * PI * 6.0), 2.0);         // nervature radiali
    float fine   = pow(abs(sin(uM * PI * 12.0 + ring * 3.0)), 3.0);  // dettaglio sottile

    float orn = 0.30 + 1.00 * n1;
    float n3 = fbm3(vec2(u * 30.0 + 7.3, d * 45.0));                 // micro-dettaglio
    float v = ringMask * petalMask * orn;
    v *= 0.55 + 0.45 * spokes;
    v += 0.14 * n2 * ringMask * petalMask;
    v += 0.12 * fine * ringMask * petalMask * detailFade;
    v += 0.10 * n3 * ringMask * petalMask * detailFade;
    v = clamp(v, 0.0, 1.0);
    v = pow(v, 1.15);

    // ---- raggi radiali luminosi (come nel video) ----
    float rays = pow(abs(sin(ang * (K * 3.0) + n1 * 2.0)), 6.0);
    rays *= smoothstep(0.35, 1.10, r);

    // ---- luminosita' guidata dall'audio ----
    float bright = 0.45 + 0.75 * uEnergy + 0.85 * uPulse + 0.30 * uGlow;

    // ---- colore: la tonalita' varia con ornamento, anello e suono ----
    float t = uHue + 0.80 * v + 0.20 * ring + 0.10 * u + 0.06 * sin(uTime * 0.30);
    vec3 col = palette(t);
    col = pow(max(col, 0.0), vec3(1.70));                  // saturo e profondo
    col *= (0.16 + 1.55 * v) * bright;

    // riflessi dorati nei punti piu' intensi
    col += vec3(1.00, 0.72, 0.30) * pow(v, 3.5) * (0.45 + 1.10 * uTreble) * bright;
    // raggi complementari
    col += palette(t + 0.5) * rays * (0.10 + 0.45 * uBass);

    // foro centrale nero + nucleo incandescente
    col *= smoothstep(0.025, 0.110, r);
    col += vec3(1.0, 0.82, 0.55) * exp(-r * r * 7000.0) * (0.30 + 1.40 * uPulse);

    // vignettatura morbida
    col *= 1.0 - 0.25 * smoothstep(0.80, 1.50, r);

    col = clamp(col, 0.0, 1.0);
    gl_FragColor = vec4(col, 1.0);
}
"""

UNIFORMS = ("uRes", "uTime", "uTravel", "uBass", "uMid", "uTreble", "uEnergy",
            "uCentroid", "uHue", "uRot", "uPulse", "uGlow",
            "uSym", "uRingScale", "uPetalW", "uMorph", "uTwist", "uNest")


def _compile(src, kind):
    sh = glCreateShader(kind)
    glShaderSource(sh, src)
    glCompileShader(sh)
    if not glGetShaderiv(sh, GL_COMPILE_STATUS):
        raise RuntimeError("Errore compilazione shader:\n" + glGetShaderInfoLog(sh).decode("utf-8", "replace"))
    return sh


class Renderer:
    def __init__(self, width, height):
        vs = _compile(VERTEX_SRC, GL_VERTEX_SHADER)
        fs = _compile(FRAGMENT_SRC, GL_FRAGMENT_SHADER)
        prog = glCreateProgram()
        glAttachShader(prog, vs)
        glAttachShader(prog, fs)
        glLinkProgram(prog)
        if not glGetProgramiv(prog, GL_LINK_STATUS):
            raise RuntimeError("Errore link program:\n" + glGetProgramInfoLog(prog).decode("utf-8", "replace"))
        glDeleteShader(vs)
        glDeleteShader(fs)
        self.prog = prog
        self.u = {name: glGetUniformLocation(prog, name) for name in UNIFORMS}
        self.width, self.height = width, height
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glDisable(GL_DEPTH_TEST)

    def resize(self, width, height):
        self.width, self.height = max(1, width), max(1, height)
        glViewport(0, 0, self.width, self.height)

    def draw(self, st):
        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(self.prog)
        loc = self.u
        glUniform2f(loc["uRes"], float(self.width), float(self.height))
        glUniform1f(loc["uTime"], st["time"])
        glUniform1f(loc["uTravel"], st["travel"])
        glUniform1f(loc["uBass"], st["bass"])
        glUniform1f(loc["uMid"], st["mid"])
        glUniform1f(loc["uTreble"], st["treble"])
        glUniform1f(loc["uEnergy"], st["energy"])
        glUniform1f(loc["uCentroid"], st["centroid"])
        glUniform1f(loc["uHue"], st["hue"])
        glUniform1f(loc["uRot"], st["rot"])
        glUniform1f(loc["uPulse"], st["pulse"])
        glUniform1f(loc["uGlow"], st["glow"])
        glUniform1f(loc["uSym"], st["sym"])
        glUniform1f(loc["uRingScale"], st["ring_scale"])
        glUniform1f(loc["uPetalW"], st["petal_w"])
        glUniform1f(loc["uMorph"], st["morph"])
        glUniform1f(loc["uTwist"], st["twist"])
        glUniform1f(loc["uNest"], st["nest"])
        glBegin(GL_QUADS)
        glVertex2f(-1.0, -1.0)
        glVertex2f(1.0, -1.0)
        glVertex2f(1.0, 1.0)
        glVertex2f(-1.0, 1.0)
        glEnd()
        glUseProgram(0)


class Hud:
    """Testo sovrapposto (info traccia + scorciatoie) disegnato con la fixed pipeline."""

    def __init__(self):
        try:
            self.font = pygame.font.SysFont("consolas,segoeui", 16)
            self.font_small = pygame.font.SysFont("consolas,segoeui", 13)
        except Exception:
            self.font = pygame.font.Font(None, 18)
            self.font_small = pygame.font.Font(None, 15)
        self.surface = None
        self.tex = None
        self._dirty = True

    def set_lines(self, lines):
        if not lines:
            if self.surface is not None:
                self.surface = None
                self._dirty = True
            return
        pads = 8
        rendered = [self.font.render(l, True, (235, 238, 245)) for l in lines[:1]]
        rendered += [self.font_small.render(l, True, (200, 206, 218)) for l in lines[1:]]
        w = max(s.get_width() for s in rendered) + pads * 2
        h = sum(s.get_height() for s in rendered) + pads * 2 + 2 * (len(rendered) - 1)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((8, 9, 14, 165))
        pygame.draw.rect(surf, (90, 140, 220, 120), surf.get_rect(), 1)
        y = pads
        for s in rendered:
            surf.blit(s, (pads, y))
            y += s.get_height() + 2
        self.surface = surf
        self._dirty = True

    def draw(self, screen_w, screen_h):
        if self.surface is None:
            return
        surf = self.surface
        w, h = surf.get_size()
        if self._dirty or self.tex is None:
            raw = pygame.image.tostring(surf, "RGBA", False)
            if self.tex is None:
                self.tex = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.tex)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, raw)
            self._dirty = False
        else:
            glBindTexture(GL_TEXTURE_2D, self.tex)

        margin = 16
        x0, y0 = margin, screen_h - h - margin

        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_TEXTURE_2D)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, screen_w, screen_h, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 0.0); glVertex2f(x0, y0)
        glTexCoord2f(1.0, 0.0); glVertex2f(x0 + w, y0)
        glTexCoord2f(1.0, 1.0); glVertex2f(x0 + w, y0 + h)
        glTexCoord2f(0.0, 1.0); glVertex2f(x0, y0 + h)
        glEnd()

        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glDisable(GL_TEXTURE_2D)
        glDisable(GL_BLEND)


def save_screenshot(path):
    try:
        w, h = pygame.display.get_window_size()
    except Exception:
        w, h = pygame.display.get_surface().get_size()
    buf = glReadPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE)
    surf = pygame.image.fromstring(bytes(buf), (w, h), "RGB", True)
    pygame.image.save(surf, path)
    return path
