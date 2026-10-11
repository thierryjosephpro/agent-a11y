"""
Indicateurs de progression portables : chrono + spinner.

Contraintes (validees avec l'utilisateur) :
- doit fonctionner en CMD, PowerShell ET dans les pipelines CI (GitHub/GitLab) ;
- pas de techno compliquee (pas de dependance externe).

Deux mecanismes SUPERPOSES :
1) des messages d'etape (print flush=True) -> s'affichent PARTOUT ;
2) un spinner anime -> UNIQUEMENT en terminal interactif (isatty()) ; en CI il
   est desactive automatiquement, il ne reste alors que les messages d'etape.
"""

import sys
import threading
import time
import itertools


def is_interactive() -> bool:
    """Vrai si la sortie est un vrai terminal (CMD/PowerShell), faux en CI/log."""
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


class Spinner:
    """Spinner sur une seule ligne, actif seulement en terminal interactif.

    En CI (isatty() faux), il n'anime rien : il affiche juste le message une
    fois, au debut. Utilisation :
        with Spinner("analyse en cours"):
            ... tache longue ...
    """

    _FRAMES = ["|", "/", "-", "\\"]

    def __init__(self, message: str):
        self.message = message
        self._stop = threading.Event()
        self._thread = None
        self._interactive = is_interactive()

    def __enter__(self):
        # Message d'etape : affiche PARTOUT (interactif comme CI).
        print(f"  {self.message}...", flush=True)
        if self._interactive:
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        return self

    def _spin(self):
        for frame in itertools.cycle(self._FRAMES):
            if self._stop.is_set():
                break
            # \r ramene le curseur en debut de ligne (interactif seulement).
            sys.stdout.write(f"\r  {frame} {self.message}... ")
            sys.stdout.flush()
            time.sleep(0.15)

    def __exit__(self, exc_type, exc, tb):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        if self._interactive:
            # efface la ligne du spinner
            sys.stdout.write("\r" + " " * (len(self.message) + 12) + "\r")
            sys.stdout.flush()
        return False


class Timer:
    """Chronometre simple. Utilisation :
        with Timer() as t:
            ...
        print(t.human())   # ex. "143.2 s (2.4 min)"
    """

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.elapsed = time.perf_counter() - self.start
        return False

    def human(self) -> str:
        e = getattr(self, "elapsed", time.perf_counter() - self.start)
        return f"{e:.1f} s ({e/60:.1f} min)"
