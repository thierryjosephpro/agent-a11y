"""
Flux "code" : audit deterministe via axe-core injecte dans le DOM.

Couvre la fraction mecaniquement decidable des criteres WCAG : contrastes,
textes alternatifs, etiquettes de formulaire, attributs ARIA, ordre des titres,
langue de la page, etc. Meme page -> meme resultat (deterministe, sans IA).

Retourne une liste de constats conformes au schema du projet.
"""

import wcag
from schemas import clean_findings

# Traduction de l'impact axe -> notre severite.
_IMPACT_TO_SEVERITY = {
    "critical": "critique",
    "serious": "majeur",
    "moderate": "mineur",
    "minor": "mineur",
}


def run(session, state: str = "initial") -> list[dict]:
    """Execute axe-core sur la page courante et renvoie les constats."""
    print("[flux code] injection d'axe-core et analyse du DOM...")
    session.inject_axe()

    # On lance axe sur les regles WCAG 2.x niveaux A et AA.
    axe_options = {
        "runOnly": {
            "type": "tag",
            "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"],
        }
    }
    result = session.page.evaluate(
        """async (options) => await axe.run(document, options)""",
        axe_options,
    )

    findings = []
    for violation in result.get("violations", []):
        rule_id = violation.get("id", "")
        crit, level = wcag.from_axe_rule(rule_id)
        impact = violation.get("impact") or "moderate"
        severity = _IMPACT_TO_SEVERITY.get(impact, "mineur")

        # Titre + description EN FRANCAIS (axe renvoie de l'anglais).
        titre_fr, desc_fr = wcag.from_axe_rule_fr(rule_id)
        titre = f"[{rule_id}] {titre_fr}"

        # Un constat par element concerne (limite a 5 pour rester lisible).
        nodes = violation.get("nodes", [])[:5]
        for node in nodes:
            selector = ""
            target = node.get("target", [])
            if target:
                selector = target[0] if isinstance(target[0], str) else str(target[0])
            findings.append({
                "source": "code",
                "wcag": crit,
                "level": level,
                "severity": severity,
                "title": titre,
                "description": desc_fr,
                "selector": selector,
                "recommendation": violation.get("helpUrl", ""),
                "state": state,
            })
        if not nodes:  # violation sans noeud precis
            findings.append({
                "source": "code",
                "wcag": crit,
                "level": level,
                "severity": severity,
                "title": titre,
                "description": desc_fr,
                "state": state,
            })

    findings = clean_findings(findings, source="code")
    print(f"[flux code] {len(findings)} constat(s) retenu(s).")
    return findings
