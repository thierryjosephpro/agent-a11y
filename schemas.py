"""
Schema strict des constats (findings) et validation.

Chaque flux (code / clavier / visuel) doit produire une liste de constats qui
respectent EXACTEMENT ce schema. C'est le garde-fou anti-hallucination : toute
sortie non conforme (notamment celle du modele de vision) est rejetee ou
nettoyee avant d'entrer dans l'agregation.
"""

from jsonschema import Draft7Validator

# Niveaux WCAG acceptes et sources de flux autorisees.
WCAG_LEVELS = ["A", "AA", "AAA"]
SOURCES = ["code", "clavier", "visuel"]
SEVERITIES = ["critique", "majeur", "mineur", "info"]

FINDING_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "source", "wcag", "level", "severity", "title", "description",
    ],
    "properties": {
        "source":      {"type": "string", "enum": SOURCES},
        "wcag":        {"type": "string"},          # ex. "1.4.3"
        "level":       {"type": "string", "enum": WCAG_LEVELS},
        "severity":    {"type": "string", "enum": SEVERITIES},
        "title":       {"type": "string", "minLength": 3},
        "description": {"type": "string", "minLength": 3},
        "selector":    {"type": "string"},          # optionnel : ou est le probleme
        "recommendation": {"type": "string"},        # optionnel : comment corriger
        "state":       {"type": "string"},          # ex. "initial" | "modale-ouverte"
        "tile_index":  {"type": "integer"},         # optionnel : num tuile (flux visuel SEQ)
        "tile_file":   {"type": "string"},          # optionnel : fichier tuile (pour le HTML)
    },
}

_validator = Draft7Validator(FINDING_SCHEMA)


def validate_finding(finding: dict) -> list[str]:
    """Retourne la liste des erreurs de validation (vide si le constat est valide)."""
    return [e.message for e in _validator.iter_errors(finding)]


def clean_findings(raw_findings: list[dict], source: str) -> list[dict]:
    """
    Filtre une liste de constats : ne garde que ceux conformes au schema.

    Force le champ 'source' a la valeur du flux appelant (on ne fait jamais
    confiance a la source auto-declaree, surtout venant du modele de vision).
    Les constats invalides sont ignores silencieusement mais comptes.
    """
    valid, rejected = [], 0
    for f in raw_findings:
        if not isinstance(f, dict):
            rejected += 1
            continue
        f = dict(f)              # copie defensive
        f["source"] = source     # on impose la source reelle
        # normaliser la severite : le modele invente parfois "Moyenne", "erreur"...
        sev = str(f.get("severity", "")).strip().lower()
        _sev_map = {
            "critique": "critique", "critical": "critique", "eleve": "critique",
            "elevee": "critique", "haute": "critique",
            "majeur": "majeur", "majeure": "majeur", "high": "majeur", "erreur": "majeur",
            "moyenne": "mineur", "moyen": "mineur", "medium": "mineur",
            "mineur": "mineur", "mineure": "mineur", "faible": "mineur",
            "basse": "mineur", "low": "mineur",
            "info": "info", "information": "info",
        }
        f["severity"] = _sev_map.get(sev, "mineur")
        f.setdefault("level", "A")
        errors = validate_finding(f)
        if errors:
            rejected += 1
            continue
        valid.append(f)
    if rejected:
        print(f"  [schema] {rejected} constat(s) rejete(s) pour non-conformite ({source})")
    return valid
