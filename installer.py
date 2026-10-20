# -*- coding: utf-8 -*-
"""
PSYSUONO - Programma di installazione (file unico).

Cosa fa:
  1. estrae PSYSUONO.exe (portabile, non richiede Python) in
     %LOCALAPPDATA%\\PSYSUONO
  2. crea i collegamenti nel menu Start e sul desktop
  3. crea il collegamento "Disinstalla PSYSUONO"
  4. propone di avviare subito il programma
"""

import ctypes
import os
import shutil
import subprocess
import sys

APP = "PSYSUONO"
EXE_NAME = "PSYSUONO.exe"
DESC = "PSYSUONO - tunnel audio-visivo kaleidoscopico"
SILENT = "--silent" in sys.argv        # nessuna finestra di dialogo (uso automatico)

UNINSTALL_PS1 = r"""$app = "PSYSUONO"
Stop-Process -Name "PSYSUONO" -Force -ErrorAction SilentlyContinue
$programs = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
Remove-Item (Join-Path $programs "$app.lnk") -ErrorAction SilentlyContinue
Remove-Item (Join-Path $programs "$app") -Recurse -ErrorAction SilentlyContinue
Remove-Item (Join-Path ([Environment]::GetFolderPath('Desktop')) "$app.lnk") -ErrorAction SilentlyContinue
$dir = Join-Path $env:LOCALAPPDATA $app
$cmd = "Start-Sleep -Seconds 2; Remove-Item -LiteralPath '" + $dir + "' -Recurse -Force -ErrorAction SilentlyContinue"
Start-Process powershell -ArgumentList '-NoProfile','-WindowStyle','Hidden','-Command',$cmd -WindowStyle Hidden
"""

UNINSTALL_BAT = (
    "@echo off\r\n"
    "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0disinstalla.ps1\"\r\n"
)


def bundle_dir():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def install_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), APP)


def msgbox(text, title=APP, flags=0x40):
    """0x40 = icona info, 0x24 = si/no + icona domanda, 0x10 = errore."""
    if SILENT:
        print(text)
        return 7                                       # IDNO
    try:
        return ctypes.windll.user32.MessageBoxW(0, text, title, flags)
    except Exception:
        return 0


def make_shortcut(lnk_path, target, workdir, desc, args=""):
    ps = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
        "$s.TargetPath = '{tgt}'; $s.Arguments = '{args}';"
        "$s.WorkingDirectory = '{wd}'; $s.Description = '{desc}'; $s.Save()"
    ).format(lnk=lnk_path.replace("'", "''"), tgt=target.replace("'", "''"),
             args=args.replace("'", "''"), wd=workdir.replace("'", "''"),
             desc=desc.replace("'", "''"))
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                   capture_output=True, timeout=60)


def copy_into(dest, src_name, out_name=None):
    src = os.path.join(bundle_dir(), src_name)
    if not os.path.isfile(src):
        raise RuntimeError("File mancante nel pacchetto: %s" % src_name)
    shutil.copy2(src, os.path.join(dest, out_name or src_name))


def main():
    dest = install_dir()
    msgbox("Benvenuto nell'installazione di PSYSUONO.\n\n"
           "Il programma verrà installato in:\n%s\n\n"
           "File: programma autonomo, non richiede Python.\n"
           "Premi OK per continuare." % dest, APP, 0x40)

    try:
        os.makedirs(dest, exist_ok=True)
        if os.path.isfile(os.path.join(dest, EXE_NAME)):
            try:
                subprocess.run(["taskkill", "/IM", EXE_NAME, "/F"],
                               capture_output=True, timeout=15)
            except Exception:
                pass
        copy_into(dest, EXE_NAME)                       # programma
        try:
            copy_into(dest, "README.md")                # istruzioni
        except RuntimeError:
            pass
        with open(os.path.join(dest, "disinstalla.ps1"), "w",
                  encoding="utf-8-sig") as fh:
            fh.write(UNINSTALL_PS1)
        with open(os.path.join(dest, "disinstalla.bat"), "w",
                  encoding="utf-8-sig") as fh:
            fh.write(UNINSTALL_BAT)

        exe = os.path.join(dest, EXE_NAME)
        bat = os.path.join(dest, "disinstalla.bat")
        programs = os.path.join(os.environ.get("APPDATA", ""),
                                "Microsoft", "Windows", "Start Menu", "Programs")
        start_dir = os.path.join(programs, APP)
        os.makedirs(start_dir, exist_ok=True)
        desktop = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")

        make_shortcut(os.path.join(start_dir, "%s.lnk" % APP), exe, dest, DESC)
        make_shortcut(os.path.join(desktop, "%s.lnk" % APP), exe, dest, DESC)
        make_shortcut(os.path.join(start_dir, "Disinstalla %s.lnk" % APP),
                      bat, dest, "Disinstalla PSYSUONO")
    except Exception as exc:
        msgbox("Installazione non riuscita:\n\n%s\n\n"
               "Se il programma è già in esecuzione, chiudilo e riprova." % exc,
               "%s - errore" % APP, 0x10)
        return 1

    ret = msgbox("Installazione completata in:\n%s\n\n"
                 "Vuoi avviare PSYSUONO adesso?" % dest, APP, 0x24)   # MB_YESNO|MB_ICONQUESTION
    if ret == 6:                                                       # IDYES
        try:
            subprocess.Popen([exe], cwd=dest)
        except Exception as exc:
            msgbox("Impossibile avviare PSYSUONO:\n%s" % exc,
                   "%s - errore" % APP, 0x10)
            return 1
    return 0


if __name__ == "__main__":
    _code = 1
    try:
        _code = main()
    except Exception as exc:
        msgbox("Errore imprevisto:\n%s" % exc, "%s - errore" % APP, 0x10)
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(_code)
