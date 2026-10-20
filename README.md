# PSYSUONO — tunnel kaleidoscopico reattivo alla musica

Software per Windows che carica un file audio, lo riproduce e mostra a video un
**tunnel infinito** di forma mandala/kaleidoscopio (come nel video di riferimento),
in **schermo intero alla risoluzione nativa massima del monitor**.

---

## Installazione (file unico)

Doppio clic su **`dist\Installazione PSYSUONO.exe`** (37 MB, un solo file):

1. conferma con **OK** nella finestra di benvenuto;
2. il programma viene copiato in `%LOCALAPPDATA%\PSYSUONO`;
3. vengono creati i collegamenti nel **menu Start** e sul **desktop**;
4. al termine puoi avviarlo subito con **Sì**.

Non serve Python né alcun altro programma: `PSYSUONO.exe` è autonomo
(`ffmpeg` è solo un acceleratore opzionale).

**Disinstalla**: collegate "Disinstalla PSYSUONO" nel menu Start, oppure
esegui `%LOCALAPPDATA%\PSYSUONO\disinstalla.bat`.

> Nota: essendo un eseguibile non firmato, Windows può mostrare il banner
> "Protetto da Windows" → clicca su *Ulteriori informazioni* → *Esegui comunque*.

---

Il tunnel **cambia colore, velocità e forma** in tempo reale con l'andamento del suono:

| Parametro audio          | Cosa pilota                                             |
|--------------------------|---------------------------------------------------------|
| Bassi (30–140 Hz)        | **velocità** di avanzamento del tunnel, densità anelli   |
| Energia RMS              | luminosità, larghezza dei petali                         |
| Colpi di basso (transitori) | lampi, torsione a spirale, **cambio di simmetria**     |
| Medie (500–2000 Hz)      | morfatura degli ornamenti, rotazione                     |
| Alti / aria (2–14 kHz)   | riflessi dorati, apertura delle fughe                    |
| Centroide spettrale      | incastro della mandala annidata + tonalità di colore     |
| Spettro complessivo      | **rotazione della palette** (colore)                     |

---

## Requisiti

- Windows 10 / 11
- Python 3.10+ (testato con 3.13)
- `ffmpeg` **opzionale** (già presente su questo PC): serve solo a decodificare
  rapidamente file MP3/FLAC/M4A; senza ffmpeg si usa il decodificatore integrato
  di SDL (WAV/MP3/OGG).

## Installazione (una tantum)

```bat
py -m pip install pygame numpy PyOpenGL
```

## Avvio da sorgente (senza installare)

Doppio clic su **`avvia.bat`**, oppure da prompt:

```bat
py main.py                     & rem schermo intero, risoluzione nativa
py main.py "C:\musica\brano.mp3"
py main.py --windowed          & rem finestra 1280x720
py main.py --monitor 1         & rem forza il monitor n. 1
py main.py --speed 1.5         & rem velocità base del tunnel x1,5
```

All'avvio senza file: si può **trascinare un file audio sulla finestra** oppure
premere `O` per sceglierlo con il dialogo di Windows.

## Controlli

| Tasto   | Azione                                             |
|---------|----------------------------------------------------|
| `SPAZIO`| pausa / riprendi                                   |
| `F`     | **schermo intero ↔ finestra**                      |
| `O`     | apri file audio                                    |
| `<` `>` | indietro / avanti 10 secondi                       |
| `+` `-` | volume                                             |
| `[` `]` | velocità del tunnel − / +                          |
| `R`     | azzera la velocità del tunnel                      |
| `S`     | salva screenshot PNG                                |
| `TAB`   | mostra/nascondi HUD                                |
| `H`     | mostra/nascondi scorciatoie                        |
| `ESC`   | esci                                               |

## Come funziona

1. **Decodifica**: l'intero brano viene decodificato in PCM mono 44,1 kHz
   (ffmpeg, oppure SDL come fallback).
2. **Analisi FFT**: finestra 2048 campioni, passo 512 (~11,6 ms) → bande
   basso/medi/alti/aria + RMS + centroide, normalizzate per traccia.
3. **Sincronizzazione**: l'orologio di riproduzione (pausa/seek/loop) indicizza i
   frame spettrali alla posizione di ascolto.
4. **Rendering**: uno shader OpenGL disegna il tunnel — prospettiva `1/r`,
   piega kaleidoscopica a simmetria variabile, anelli con fughe nere, ornamenti
   frattali e palette coseno — a piena risoluzione del monitor, con VSync.

## Opzioni da riga di comando

```
file             file audio da caricare
--windowed       avvia in finestra (default: schermo intero)
--monitor N      usare il monitor di indice N (default: quello sotto il cursore)
--speed X        moltiplicatore di velocità iniziale (0.1 – 5)
--smoke N        prova tecnica: renderizza N frame, salva screenshot ed esce
--shot percorso  percorso dello screenshot di prova
```

## Risoluzione massima

All'avvio il processo si dichiara *DPI-aware*, quindi vengono usati i **pixel
fisici** del monitor (es. 2560×1440 o 3840×2160, non quelli scalati da Windows).
Il full screen viene applicato al monitor sotto il cursore: con più monitor si
può sceglierne uno con `--monitor N` o spostando la finestra prima di premere `F`.
