"""
Orchestrateur de l'agent d'accessibilite.

Pipeline (deterministe, scripte) :
    ouvrir la page  ->  flux code  ->  flux clavier  ->  flux visuel
                    ->  agregation  ->  ecriture du rapport local

C'est un WORKFLOW oriente outils (et non un agent autonome) : l'enchainement
est fixe, ce qui garantit la reproductibilite exigee par le protocole
d'evaluation. Le modele de vision est confine a une seule tache (jugement
perceptuel), il ne pilote pas le parcours.

Usage :
    python run.py                         # audite la page de test livree
    python run.py <URL>                   # audite une URL
    python run.py <fichier.html>          # audite une page locale
    python run.py <image.png>             # analyse visuelle SEULE d'une image
    python run.py <A> <B> <C> ...         # plusieurs cibles (URLs / fichiers / images)
    python run.py "test_page/*"           # toutes les pages d'un dossier (glob)
    python run.py test_page/              # tous les fichiers d'un dossier
    python run.py --no-visual <...>       # saute le flux visuel (ex. sans Ollama)

Chaque cible produit son propre rapport horodate (output/AAAA-MM-JJ-HH-MM-SS.*)
plus les noms fixes rapport.md / rapport.html / findings.json (dernier run).
"""

import sys
import glob
import time
from pathlib import Path
from datetime import datetime

import config
import exec_log
from aggregate import aggregate, write_reports
from flows import flow_code, flow_keyboard, flow_visual
from flows.collector import BrowserSession
from flows.progress import Spinner


# --- Resolution des cibles ---------------------------------------------------

def _looks_like_url(s: str) -> bool:
    return s.startswith(("http://", "https://", "file://"))


def _is_image(path: str) -> bool:
    return Path(path).suffix.lower() in config.IMAGE_EXTENSIONS


def resolve_targets(args: list[str]) -> list[str]:
    """Transforme les arguments en liste de cibles concretes.

    - URL (http/https/file) : gardee telle quelle.
    - Dossier : remplace par tous les fichiers qu'il contient.
    - Motif glob (ex. test_page/*) : etendu.
    - Fichier (html, image...) : garde tel quel.
    """
    targets = []
    for a in args:
        if _looks_like_url(a):
            targets.append(a)
            continue
        p = Path(a)
        if p.is_dir():
            targets += sorted(str(f) for f in p.iterdir() if f.is_file())
        elif any(ch in a for ch in "*?[]"):
            targets += sorted(glob.glob(a))
        else:
            targets.append(a)
    return targets


def _as_navigable(target: str) -> str:
    """Pour un fichier local (non-image), renvoie une URL file:// absolue."""
    if _looks_like_url(target):
        return target
    return Path(target).resolve().as_uri()


# --- Audit d'une cible -------------------------------------------------------

def audit_one(target: str, use_visual: bool = True) -> int:
    """Audite une seule cible. Retourne le nombre de constats."""
    start = time.perf_counter()
    debut = datetime.now()
    paths = config.report_paths(debut)

    print("=" * 64)
    print(" Agent d'accessibilite libre de droits — audit hybride")
    print(f" Cible : {target}")
    print(f" Debut : {debut:%Y-%m-%d %H:%M:%S}")
    print("=" * 64)

    all_findings: list[dict] = []

    if _is_image(target):
        # --- Cible = IMAGE STATIQUE : flux visuel SEUL (pas de DOM) ----------
        print("  [mode] image statique -> flux visuel uniquement "
              "(pas de flux code ni clavier : aucun DOM a analyser).")
        img_path = Path(target)
        if not img_path.exists():
            print(f"  [erreur] image introuvable : {target}")
            return 0
        if use_visual:
            with Spinner("analyse visuelle en cours (1-3 min selon le materiel)"):
                visual_findings = flow_visual.run(
                    None, img_path, known_facts=[], state="initial",
                )
            all_findings += visual_findings
        else:
            print("[flux visuel] saute (--no-visual) -> rien a analyser sur une image.")
    else:
        # --- Cible = PAGE WEB : pipeline hybride complet ---------------------
        url = _as_navigable(target)
        screenshot_path = config.OUTPUT_DIR / "capture.png"
        with BrowserSession(url) as session:
            code_findings = flow_code.run(session, state="initial")
            all_findings += code_findings

            session.screenshot(screenshot_path)

            if use_visual:
                with Spinner("analyse visuelle en cours (1-3 min selon le materiel)"):
                    visual_findings = flow_visual.run(
                        session, screenshot_path,
                        known_facts=code_findings, state="initial",
                    )
                all_findings += visual_findings
            else:
                print("[flux visuel] saute (--no-visual).")

            keyboard_findings = flow_keyboard.run(session, state="initial")
            all_findings += keyboard_findings

    # --- Agregation + rapports (horodates + fixes) --------------------------
    print("-" * 64)
    findings = aggregate(all_findings)
    write_reports(findings, target_url=target, paths=paths)

    print("-" * 64)
    fin = datetime.now()
    duree = time.perf_counter() - start

    # --- Journal d'execution (1 ligne par cible : config, modele, temps) -----
    exec_log.append(debut, fin, duree, target, findings)

    print(f" Termine : {len(findings)} constat(s). Voir {paths['html']}")
    print(f" Backend : {config.VISION_BACKEND} | Modele : {config.active_model()}")
    print(f" Debut : {debut:%Y-%m-%d %H:%M:%S}   Fin : {fin:%Y-%m-%d %H:%M:%S}")
    print(f" Temps total : {duree:.1f} s ({duree/60:.1f} min)")
    print("=" * 64)
    return len(findings)


def main(targets: list[str], use_visual: bool = True) -> None:
    if not targets:
        targets = [config.TARGET_URL]
    total = len(targets)
    if total > 1:
        print(f"### {total} cible(s) a auditer ###\n")
    for i, target in enumerate(targets, start=1):
        if total > 1:
            print(f"\n######## Cible {i}/{total} ########")
        try:
            audit_one(target, use_visual=use_visual)
        except Exception as exc:  # une cible qui plante n'arrete pas les autres
            print(f" [erreur] echec sur '{target}' : {exc}")
    if total > 1:
        print(f"\n### Termine : {total} cible(s) auditee(s). "
              f"Rapports horodates dans {config.OUTPUT_DIR} ###")


if __name__ == "__main__":
    args = sys.argv[1:]
    use_visual = "--no-visual" not in args
    args = [a for a in args if a != "--no-visual"]
    targets = resolve_targets(args) if args else []
    main(targets, use_visual=use_visual)
