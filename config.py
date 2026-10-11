"""
Configuration centrale de l'agent d'accessibilite.

Tout est parametrable ici : l'URL a auditer, le point d'API Ollama, le modele
de vision, les chemins de sortie et les reglages des differents flux.

Le CODE de l'agent ne depend pas du materiel (Intel / NVIDIA / CPU) : il appelle
toujours la meme API locale Ollama. Le choix du moteur se fait en dehors du
code, via start-ollama.bat.

Deux reglages, en revanche, adaptent le FLUX VISUEL a la contrainte rencontree
sur certains materiels (voir la section "Decoupage / tuilage" plus bas). Ils se
pilotent par variables d'environnement, avec des valeurs sures codees en dur.
"""

import os
from enum import Enum
from pathlib import Path

# --- Chemins du projet -------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
VENDOR_DIR = BASE_DIR / "vendor"
AXE_LOCAL_PATH = VENDOR_DIR / "axe.min.js"          # axe-core vendorise (local)
TEST_PAGE = (BASE_DIR / "test_page" / "index.html").as_uri()  # page a defauts semes

# --- Cible de l'audit --------------------------------------------------------
# Par defaut on audite la page de test livree avec le projet.
# Remplacez par n'importe quelle URL (http://..., https://..., file://...).
TARGET_URL = TEST_PAGE

# --- Ollama (moteur d'inference local) ---------------------------------------
OLLAMA_HOST = "http://localhost:11434"
VISION_MODEL = "qwen2.5vl:7b"       # modele de vision libre de droits (Apache 2.0)

# --- Choix du backend de vision ---------------------------------------------
# VISION_BACKEND pilote QUEL modele repond au flux visuel :
#   "ollama" (DEFAUT) : modele local libre de droits (Qwen2.5-VL via Ollama).
#   "claude"          : API Anthropic (point de COMPARAISON, payant, non local).
#   "gemini"          : API Google Gemini (point de COMPARAISON, palier gratuit).
# Le mode local reste le defaut : les backends commerciaux servent UNIQUEMENT a
# produire des donnees de comparaison (local vs commercial). Ils ne s'activent
# que si la cle API correspondante est fournie en variable d'environnement.
VISION_BACKEND = os.environ.get("VISION_BACKEND", "ollama").strip().lower()

# Noms de modele par backend (surchargables par variable d'environnement).
# ATTENTION : les noms de modeles commerciaux changent avec le temps. Si l'appel
# echoue avec "modele introuvable", ajustez CLAUDE_MODEL / GEMINI_MODEL d'apres
# la documentation du fournisseur (docs.claude.com / ai.google.dev).
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash") #gemini-3.8-flash #gemini-3.5-flash-lite

# Cles API : lues en variable d'environnement (JAMAIS en dur dans le code).
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Endpoints et delais des API commerciales.
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
API_TIMEOUT = 120                  # secondes (API distantes)


def active_model() -> str:
    """Nom lisible du modele reellement utilise par le flux visuel (pour le log)."""
    if VISION_BACKEND == "claude":
        return f"claude:{CLAUDE_MODEL}"
    if VISION_BACKEND == "gemini":
        return f"gemini:{GEMINI_MODEL}"
    return f"ollama:{VISION_MODEL}"
# Timeout genereux : sur CPU une inference vision peut depasser 9 min ; sur GPU
# Intel (768px) ~3 min. 900 s = 15 min laisse de la marge dans tous les cas.
OLLAMA_TIMEOUT = 900               # secondes

# --- Navigateur (Playwright) -------------------------------------------------
# HEADLESS pilotable par variable d'environnement (comme AGENT_TILING, etc.).
# Defaut True : adapte a une execution automatisee / CI (GitLab, GitHub Actions).
# Mettre HEADLESS=False pour une fenetre visible (demo, debogage).
#   PowerShell : $env:HEADLESS = "False"
#   bash/CI    : HEADLESS=False python run.py ...
# NB : en mode True, Playwright utilise "chromium-headless-shell". S'il n'est pas
# installe, voir le README (section "Executer en mode headless").
HEADLESS = os.environ.get("HEADLESS", "True").strip().lower() not in ("0", "false", "no", "")
VIEWPORT = {"width": 1280, "height": 900}
NAV_TIMEOUT = 30_000               # ms

# --- Flux clavier ------------------------------------------------------------
MAX_TAB_STOPS = 40                 # nb max de Tab avant d'arreter le parcours

# --- Interaction pour reveler l'etat post-interaction ------------------------
# Sur la page de test, un defaut n'apparait qu'apres avoir ouvert la modale.
# On indique ici le declencheur et la modale a inspecter. Mettre a None pour
# desactiver (ex. sur un site tiers sans modale connue).
MODAL_TRIGGER_SELECTOR = "#open-modal"
MODAL_SELECTOR = "#demo-modal"

# =============================================================================
#  Decoupage / tuilage du flux visuel
# =============================================================================
# Contexte : un modele vision (VLM) ne peut pas analyser correctement une image
# de page tres haute :
#   - sur iGPU Intel (SYCL), une image dont une dimension depasse ~1024 px fait
#     CRASHER le kernel (work-group > 1024) ;
#   - sur TOUT materiel (CPU, NVIDIA inclus), ecraser une page longue en une
#     seule image la rend illisible (le modele boucle / hallucine).
#
# La reponse est de DECOUPER la page en tuiles a resolution native (crops, sans
# redimensionnement destructeur). Deux reglages, hierarchises :
#
#   1) AGENT_TILING  (option "mere")  -> FAUT-IL decouper ?
#   2) TILING_STRATEGY (option "fille") -> COMMENT recoller l'information ?
#      (ne s'applique QUE si le decoupage est actif)
#
# Les valeurs concretes (tailles en px) sont codees en dur dans les enums :
# la variable d'environnement ne fait que SELECTIONNER un profil, jamais saisir
# une dimension libre.


class TilingMode(Enum):
    """Option mere : quand decouper l'image avant de l'envoyer au modele.

    La valeur = taille max d'une tuile en px (multiple de 28, la taille de patch
    de Qwen2.5-VL), ou None si aucun decoupage.
    """
    OFF = None          # pas de decoupage : 1 seule image. Defaut. Cas CPU /
                        # NVIDIA / page courte. Le modele recoit la capture telle
                        # quelle (eventuellement reduite, voir MAX_SINGLE_DIM).
    IGPU_SYCL = 1008    # tuiles de 1008 px max : contourne le crash SYCL de
                        # l'iGPU Intel Arc (< 1024) tout en restant lisible.
    SAFE_SMALL = 756    # tuiles plus petites (marge de securite maximale) si
                        # 1008 pose encore probleme sur un materiel donne.


class TilingStrategy(Enum):
    """Option fille : comment presenter les tuiles au modele (si decoupage actif).

    N'a d'effet que lorsque TilingMode != OFF. Ces strategies sont UNIVERSELLES
    (elles ne dependent pas du materiel) : elles repondent a "comment analyser
    une page longue decoupee en morceaux".
    """
    LOT = "LOT"   # toutes les tuiles envoyees en UN SEUL appel (par lot).
                  # Oppose a SEQ. Teste : inefficace sur le 7B (le multi-images
                  # le fait echouer / halluciner), MAIS potentiellement viable
                  # sur un modele plus puissant (72B, cloud) -> a reevaluer en V2.
    LOT_VUE = "LOT_VUE"   # LOT + une vue d'ensemble reduite (contexte).
                  # Variante de LOT. Meme limite multi-images sur 7B -> V2.
    LOT_ANCRAGE = "LOT_ANCRAGE"   # LOT_VUE + ancrage spatial (position de chaque
                  # tuile decrite dans le prompt). Variante la plus riche.
                  # Meme limite multi-images sur 7B -> a reevaluer en V2.
    SEQ = "SEQ"  # UNE tuile par appel, en boucle (N appels au lieu d'1). Chaque
                 # tuile est analysee SEULE -> joue sur la force du modele (mono-
                 # image) et evite la saturation de contexte. Plus lent mais
                 # concu pour les pages longues.

# --- Selection par variables d'environnement (valeurs sures par defaut) -------
def _tiling_mode_from_env():
    name = os.environ.get("AGENT_TILING", "OFF").strip().upper()
    try:
        return TilingMode[name]
    except KeyError:
        print(f"  [config] AGENT_TILING='{name}' inconnu -> OFF par defaut "
              f"(valeurs: {', '.join(m.name for m in TilingMode)})")
        return TilingMode.OFF


def _tiling_strategy_from_env():
    # Defaut = SEQ : la seule strategie validee (une tuile par appel). LOT et ses
    # variantes sont conservees pour la V2 mais echouent sur le 7B (multi-images).
    name = os.environ.get("TILING_STRATEGY", "SEQ").strip().upper()
    try:
        return TilingStrategy[name]
    except KeyError:
        print(f"  [config] TILING_STRATEGY='{name}' inconnu -> SEQ par defaut "
              f"(valeurs: {', '.join(s.name for s in TilingStrategy)})")
        return TilingStrategy.SEQ


# Debug : afficher la reponse brute du modele de vision.
# Desactive par defaut ; activer avec la variable d'environnement AGENT_DEBUG=1.
AGENT_DEBUG = os.environ.get("AGENT_DEBUG", "0").strip().lower() not in ("", "0", "false", "no")

TILING_MODE = _tiling_mode_from_env()
TILING_STRATEGY = _tiling_strategy_from_env()

# Chevauchement entre tuiles voisines (px) : evite de couper un element pile sur
# une frontiere ; les doublons eventuels sont fusionnes a l'agregation.
TILE_OVERLAP = 80

# Reste de tuile plus petit que ce seuil (px) : ignore (bande trop fine pour
# contenir quoi que ce soit d'exploitable, evite un appel modele inutile).
TILE_MIN_REMAINDER = 60

# En mode OFF, si la capture depasse cette dimension, on la reduit quand meme a
# cette valeur (garde-fou : evite d'envoyer une image geante). None = jamais.
# MAX_SINGLE_DIM = 1280
MAX_SINGLE_DIM = 768

# En mode d'appel au modele : forcer la sortie JSON cote Ollama ("format":"json").
# ATTENTION : sur la build Ollama accelere Intel (IPEX-LLM), cette contrainte de
# grammaire fait CRASHER le runner. On la laisse donc a False par defaut (le
# prompt + l'extracteur JSON robuste suffisent). A ne passer a True que sur un
# moteur ou la grammaire JSON est stable (ex. Ollama standard CPU/NVIDIA).
USE_OLLAMA_JSON_FORMAT = False

# --- Pre-filtre des tuiles unies (strategie SEQ) -----------------------------
# Avant d'envoyer une tuile au modele, on mesure son uniformite (sans IA). Une
# tuile quasi-unie (ratio de la couleur dominante >= seuil) est IGNOREE : pas
# d'appel, car elle ne contient pas de contenu a auditer. Cela accelere SEQ et
# evite des faux positifs sur les zones vides.
# Reglage ICI (pas en variable d'environnement) car stable.
# 0.985 = tuile consideree unie si >= 98,5 % d'une seule teinte.
TILE_UNIFORM_THRESHOLD = 0.985

# --- Sorties -----------------------------------------------------------------
# Noms "fixes" (retro-compatibilite / dernier run). Les rapports horodates
# (un par cible) sont nommes via report_paths() ci-dessous.
REPORT_MD = OUTPUT_DIR / "rapport.md"          # rapport lisible (au lieu de la PR)
FINDINGS_JSON = OUTPUT_DIR / "findings.json"   # constats bruts agreges

# Journal des executions (CSV, en ajout) : une ligne par cible auditee.
# Permet de comparer les runs (local vs commercial) : config, modele, temps.
EXEC_LOG = OUTPUT_DIR / "execution_log.csv"


def report_paths(when=None):
    """Chemins de rapport horodates (.md / .html / .json) pour un run.

    Nom : AAAA-MM-JJ-HH-MM-SS.<ext>. Permet d'auditer plusieurs cibles sans
    ecraser les rapports precedents. Retourne un dict {md, html, json, stamp}.
    """
    from datetime import datetime
    when = when or datetime.now()
    stamp = when.strftime("%Y-%m-%d-%H-%M-%S")
    return {
        "stamp": stamp,
        "md":   OUTPUT_DIR / f"{stamp}.md",
        "html": OUTPUT_DIR / f"{stamp}.html",
        "json": OUTPUT_DIR / f"{stamp}.json",
    }


# Extensions reconnues comme "image statique" (analyse visuelle directe, sans
# navigateur : pas de flux code ni clavier).
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
