"""
Journal des exécutions (CSV, en ajout).

Une ligne par cible auditée. Objectif : comparer les runs entre eux — notamment
le modèle LOCAL (Qwen2.5-VL via Ollama) et les modèles COMMERCIAUX (Claude,
Gemini) sur les mêmes pages, à conditions égales.

Colonnes :
    debut           date-heure de début   (AAAA-MM-JJ HH:MM:SS)
    fin             date-heure de fin      (AAAA-MM-JJ HH:MM:SS)
    duree_s         durée en secondes      (1 décimale)
    cible           URL / fichier / image audité
    backend         ollama | claude | gemini   (VISION_BACKEND)
    modele          nom précis du modèle       (config.active_model())
    tiling          OFF | SAFE_SMALL | IGPU_SYCL  (AGENT_TILING)
    strategie       SEQ | LOT | LOT_VUE | LOT_ANCRAGE  (TILING_STRATEGY)
    nb_constats     total de constats retenus
    nb_visuels      constats issus du flux visuel (IA)
"""

import csv
import config

HEADER = ["debut", "fin", "duree_s", "cible", "backend", "modele",
          "tiling", "strategie", "nb_constats", "nb_visuels"]


def append(debut, fin, duree_s, cible, findings):
    """Ajoute une ligne au journal CSV (crée l'en-tête si le fichier est neuf)."""
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    nouveau = not config.EXEC_LOG.exists()
    nb_total = len(findings)
    nb_visuels = sum(1 for f in findings if f.get("source") == "visuel")
    fmt = "%Y-%m-%d %H:%M:%S"
    row = [
        debut.strftime(fmt),
        fin.strftime(fmt),
        f"{duree_s:.1f}",
        cible,
        config.VISION_BACKEND,
        config.active_model(),
        config.TILING_MODE.name,
        config.TILING_STRATEGY.name,
        nb_total,
        nb_visuels,
    ]
    with open(config.EXEC_LOG, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if nouveau:
            w.writerow(HEADER)
        w.writerow(row)
    print(f"[journal] ligne ajoutee -> {config.EXEC_LOG}")
