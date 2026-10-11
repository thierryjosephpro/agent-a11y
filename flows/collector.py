"""
Socle de collecte : Playwright, un seul navigateur, en sequentiel.

Ce module ouvre la page UNE seule fois et expose l'objet `page` aux trois flux.
C'est le principe du rapport : une ouverture alimente les flux code, clavier et
visuel, sans multiplier les navigateurs.

Utilisation :
    with BrowserSession(url) as session:
        session.screenshot(path)
        page = session.page
        ...
"""

import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

import config

# axe-core : on l'utilise en local. S'il n'est pas vendorise, on le telecharge
# une seule fois depuis un CDN (jsDelivr). Ensuite tout est 100 % local.
AXE_CDN = "https://cdn.jsdelivr.net/npm/axe-core@4/axe.min.js"


def ensure_axe() -> Path:
    """Garantit la presence locale d'axe.min.js (telechargement unique si absent)."""
    if config.AXE_LOCAL_PATH.exists() and config.AXE_LOCAL_PATH.stat().st_size > 0:
        return config.AXE_LOCAL_PATH
    print(f"  [axe] axe.min.js absent, telechargement unique depuis {AXE_CDN}")
    config.VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(AXE_CDN, config.AXE_LOCAL_PATH)
    print(f"  [axe] enregistre dans {config.AXE_LOCAL_PATH}")
    return config.AXE_LOCAL_PATH


class BrowserSession:
    """Contexte de navigateur partage par les trois flux."""

    def __init__(self, url: str):
        self.url = url
        self._pw = None
        self._browser = None
        self._context = None
        self.page = None

    def __enter__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=config.HEADLESS)
        self._context = self._browser.new_context(viewport=config.VIEWPORT)
        self.page = self._context.new_page()
        self.page.set_default_timeout(config.NAV_TIMEOUT)
        print(f"  [nav] ouverture de {self.url}")
        # self.page.goto(self.url, wait_until="networkidle")
        self.page.goto(self.url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(2500)  # laisse le rendu se stabiliser
        return self

    def screenshot(self, path: Path) -> Path:
        """Capture pleine page pour le flux visuel."""
        path.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(path), full_page=True)
        print(f"  [nav] capture enregistree : {path}")
        return path

    def inject_axe(self) -> None:
        """Injecte axe-core dans le DOM depuis le fichier local."""
        axe_path = ensure_axe()
        self.page.add_script_tag(path=str(axe_path))

    def __exit__(self, exc_type, exc, tb):
        for closer in (self._context, self._browser):
            try:
                if closer:
                    closer.close()
            except Exception:
                pass
        if self._pw:
            self._pw.stop()
