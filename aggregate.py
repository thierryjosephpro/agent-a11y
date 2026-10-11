"""
Agregation des trois flux -> rapport Markdown lisible (100 % local).

A la place de publier un commentaire sur une Pull Request (renvoye aux
perspectives dans le rapport), on ECRIT le rapport dans un fichier local
(output/rapport.md). Le contenu et la structure sont identiques ; seule la
destination change.

Etapes : fusion des constats -> dedoublonnage -> tri par priorite (niveau WCAG
puis severite) -> regroupement par critere -> generation du Markdown.
"""

import json
from collections import defaultdict
from datetime import datetime

import config
import wcag

_SEVERITY_EMOJI = {
    "critique": "[CRITIQUE]",
    "majeur": "[MAJEUR]",
    "mineur": "[MINEUR]",
    "info": "[INFO]",
}

# Libelles lisibles des flux. Le flux visuel est marque "(IA)" pour distinguer
# la source basee sur le modele (a valider) des flux deterministes (fiables).
_SOURCE_LABEL = {
    "code": "flux code",
    "clavier": "flux clavier",
    "visuel": "flux visuel (IA)",
}


def _dedupe(findings: list[dict]) -> list[dict]:
    """Supprime les doublons.

    - Flux deterministes (code, clavier) : doublon exact sur
      (critere + selecteur + titre + etat).
    - Flux visuel (IA) : les constats n'ont PAS de selecteur et leur titre /
      description varient d'une tuile a l'autre (le modele reformule). On
      dedoublonne donc par (critere + etat) : un seul constat visuel par
      critere WCAG est conserve (le premier rencontre). Evite les doublons du
      type "Hierarchie visuelle trompeuse" repete sur plusieurs tuiles.
    """
    seen = set()
    unique = []
    for f in findings:
        if f.get("source") == "visuel":
            key = ("visuel", f.get("wcag"), f.get("state", ""))
        else:
            key = (f.get("source"), f.get("wcag"), f.get("selector", ""),
                   f.get("title", ""), f.get("state", ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
    return unique


def aggregate(all_findings: list[dict]) -> list[dict]:
    """Fusionne, dedoublonne et trie les constats par priorite."""
    findings = _dedupe(all_findings)
    findings.sort(key=lambda f: wcag.priority(f.get("level", "A"), f.get("severity", "mineur")))
    return findings


def to_markdown(findings: list[dict], target_url: str = None) -> str:
    """Genere le rapport Markdown pedagogique."""
    cible = target_url or config.TARGET_URL
    total = len(findings)
    by_level = defaultdict(int)
    by_source = defaultdict(int)
    for f in findings:
        by_level[f.get("level", "A")] += 1
        by_source[f.get("source", "?")] += 1

    lines = []
    lines.append("# Rapport d'audit d'accessibilite (a11y)")
    lines.append("")
    lines.append(f"*Genere le {datetime.now():%Y-%m-%d %H:%M} — cible : `{cible}`*")
    lines.append("")
    lines.append("## Synthese")
    lines.append("")
    lines.append(f"- **{total}** constat(s) au total")
    lines.append(f"- Par niveau : "
                 f"A = {by_level.get('A', 0)}, "
                 f"AA = {by_level.get('AA', 0)}, "
                 f"AAA = {by_level.get('AAA', 0)}")
    lines.append(f"- Par flux : "
                 f"code = {by_source.get('code', 0)}, "
                 f"clavier = {by_source.get('clavier', 0)}, "
                 f"visuel = {by_source.get('visuel', 0)}")
    lines.append("")

    if total == 0:
        lines.append("Aucun defaut d'accessibilite detecte par les trois flux.")
        return "\n".join(lines)

    # Regroupement par critere WCAG.
    grouped = defaultdict(list)
    for f in findings:
        grouped[f.get("wcag", "?")].append(f)

    lines.append("## Constats detailles (par critere WCAG)")
    lines.append("")
    for crit in sorted(grouped.keys()):
        items = grouped[crit]
        level = items[0].get("level", "A")
        lines.append(f"### {crit} — {wcag.label(crit)} (niveau {level})")
        lines.append("")
        for f in items:
            tag = _SEVERITY_EMOJI.get(f.get("severity", "mineur"), "")
            src = f.get("source", "?")
            src_label = _SOURCE_LABEL.get(src, f"flux {src}")
            state = f.get("state", "")
            state_txt = f" _(etat : {state})_" if state and state != "initial" else ""
            lines.append(f"- {tag} **{f.get('title', '')}** "
                         f"— _{src_label}_{state_txt}")
            if f.get("description"):
                lines.append(f"  - {f['description']}")
            if f.get("selector"):
                lines.append(f"  - Element : `{f['selector']}`")
            reco = f.get("recommendation", "")
            if reco:
                if reco.startswith("http"):
                    lines.append(f"  - Documentation (en) : {reco}")
                else:
                    lines.append(f"  - Recommandation : {reco}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("_Rapport produit localement par l'agent d'accessibilite libre de droits "
                 "(Qwen2.5-VL + axe-core + test clavier). Perimetre : accessibilite (a11y), "
                 "non UX._")
    return "\n".join(lines)


def _html_escape(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _tile_data_uri(tile_file: str) -> str:
    """Lit une tuile de output/tiles/ et la renvoie en data URI base64 (inline)."""
    import base64
    path = config.OUTPUT_DIR / "tiles" / tile_file
    if not path.exists():
        return ""
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def to_html(findings: list[dict], target_url: str = None) -> str:
    """Genere un rapport HTML autonome (un seul fichier, images inline).

    Sous chaque constat du flux visuel (IA), affiche la tuile concernee pour
    montrer OU le modele a detecte le probleme.
    """
    cible = target_url or config.TARGET_URL
    total = len(findings)
    by_level, by_source = defaultdict(int), defaultdict(int)
    for f in findings:
        by_level[f.get("level", "A")] += 1
        by_source[f.get("source", "?")] += 1

    grouped = defaultdict(list)
    for f in findings:
        grouped[f.get("wcag", "?")].append(f)

    css = """
    body{font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:2rem auto;
         padding:0 1rem;color:#1a1a1a;line-height:1.5}
    h1{border-bottom:3px solid #0a5;padding-bottom:.3rem}
    .meta{color:#666;font-size:.9rem}
    .synth{background:#f4f6f8;border-radius:8px;padding:1rem 1.2rem;margin:1rem 0}
    h2.crit{background:#eef2f5;padding:.4rem .6rem;border-left:4px solid #0a5;margin-top:2rem}
    .finding{border:1px solid #e2e6ea;border-radius:8px;padding:.8rem 1rem;margin:.8rem 0}
    .sev{font-weight:bold;font-size:.8rem;padding:.1rem .4rem;border-radius:4px;color:#fff}
    .sev.critique{background:#c0392b}.sev.majeur{background:#e67e22}
    .sev.mineur{background:#3498db}.sev.info{background:#7f8c8d}
    .src{font-size:.8rem;color:#666;font-style:italic}
    .src.ia{color:#8e44ad;font-weight:bold}
    .tile{margin-top:.6rem;border:1px solid #ccc;border-radius:6px;max-width:100%}
    .tile-cap{font-size:.8rem;color:#666;margin-top:.4rem}
    code{background:#f0f0f0;padding:.1rem .3rem;border-radius:3px}
    footer{margin-top:2rem;color:#888;font-size:.85rem;border-top:1px solid #eee;padding-top:1rem}
    """

    h = []
    h.append("<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'>")
    h.append("<title>Rapport d'audit d'accessibilite</title>")
    h.append(f"<style>{css}</style></head><body>")
    h.append("<h1>Rapport d'audit d'accessibilite (a11y)</h1>")
    h.append(f"<p class='meta'>Genere le {datetime.now():%Y-%m-%d %H:%M} — "
             f"cible : <code>{_html_escape(cible)}</code></p>")
    h.append("<div class='synth'>")
    h.append(f"<b>{total}</b> constat(s) au total<br>")
    h.append(f"Par niveau : A = {by_level.get('A',0)}, AA = {by_level.get('AA',0)}, "
             f"AAA = {by_level.get('AAA',0)}<br>")
    h.append(f"Par flux : code = {by_source.get('code',0)}, "
             f"clavier = {by_source.get('clavier',0)}, "
             f"visuel (IA) = {by_source.get('visuel',0)}")
    h.append("</div>")

    if total == 0:
        h.append("<p>Aucun defaut d'accessibilite detecte par les trois flux.</p>")
        h.append("</body></html>")
        return "\n".join(h)

    for crit in sorted(grouped.keys()):
        items = grouped[crit]
        level = items[0].get("level", "A")
        h.append(f"<h2 class='crit'>{_html_escape(crit)} — "
                 f"{_html_escape(wcag.label(crit))} (niveau {level})</h2>")
        for f in items:
            src = f.get("source", "?")
            src_label = _SOURCE_LABEL.get(src, f"flux {src}")
            src_cls = "src ia" if src == "visuel" else "src"
            sev = f.get("severity", "mineur")
            h.append("<div class='finding'>")
            h.append(f"<span class='sev {sev}'>{sev.upper()}</span> "
                     f"<b>{_html_escape(f.get('title',''))}</b> "
                     f"<span class='{src_cls}'>— {src_label}</span>")
            if f.get("description"):
                h.append(f"<p>{_html_escape(f['description'])}</p>")
            if f.get("selector"):
                h.append(f"<p>Element : <code>{_html_escape(f['selector'])}</code></p>")
            reco = f.get("recommendation", "")
            if reco:
                if str(reco).startswith("http"):
                    h.append(f"<p>Documentation (en) : "
                             f"<a href='{_html_escape(reco)}'>{_html_escape(reco)}</a></p>")
                else:
                    h.append(f"<p>Recommandation : {_html_escape(reco)}</p>")
            # tuile concernee (flux visuel uniquement)
            if src == "visuel" and f.get("tile_file"):
                uri = _tile_data_uri(f["tile_file"])
                if uri:
                    h.append(f"<img class='tile' src='{uri}' "
                             f"alt='Tuile {f.get('tile_index','?')}'>")
                    h.append(f"<div class='tile-cap'>Zone analysee "
                             f"(tuile {f.get('tile_index','?')})</div>")
            h.append("</div>")

    h.append("<footer>Rapport produit localement par l'agent d'accessibilite "
             "libre de droits (Qwen2.5-VL + axe-core + test clavier). "
             "Perimetre : accessibilite (a11y), non UX. "
             "Les constats du flux visuel (IA) sont indicatifs et doivent etre "
             "valides par un humain.</footer>")
    h.append("</body></html>")
    return "\n".join(h)


def write_reports(findings: list[dict], target_url: str = None,
                  paths: dict = None, also_fixed: bool = True) -> None:
    """Ecrit le JSON brut, le rapport Markdown ET le rapport HTML dans output/.

    - paths : dict {md, html, json} (ex. config.report_paths()) pour des noms
      horodates, un par cible. Si None, on utilise les noms fixes historiques.
    - also_fixed : quand des chemins horodates sont fournis, ecrit EN PLUS les
      noms fixes (rapport.md / rapport.html / findings.json) qui pointent vers
      le dernier run — pratique pour la demo et la retro-compatibilite.
    """
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    md_text = to_markdown(findings, target_url)
    html_text = to_html(findings, target_url)
    json_text = json.dumps(findings, ensure_ascii=False, indent=2)

    # cibles d'ecriture : horodatees (si fournies) + fixes
    targets = []
    if paths:
        targets.append((paths["json"], paths["md"], paths["html"]))
        if also_fixed:
            targets.append((config.FINDINGS_JSON, config.REPORT_MD,
                            config.OUTPUT_DIR / "rapport.html"))
    else:
        targets.append((config.FINDINGS_JSON, config.REPORT_MD,
                        config.OUTPUT_DIR / "rapport.html"))

    for json_p, md_p, html_p in targets:
        json_p.write_text(json_text, encoding="utf-8")
        md_p.write_text(md_text, encoding="utf-8")
        html_p.write_text(html_text, encoding="utf-8")

    # journalise les chemins principaux (le 1er jeu = horodate si present)
    jp, mp, hp = targets[0]
    print(f"[agregation] constats bruts : {jp}")
    print(f"[agregation] rapport Markdown : {mp}")
    print(f"[agregation] rapport HTML     : {hp}")
