"""
Correspondance entre les regles techniques et les criteres WCAG 2.1 / 2.2.

axe-core renvoie des identifiants de regles (ex. "color-contrast"). On les
rattache ici a leur critere WCAG (ex. "1.4.3") et a leur niveau (A / AA).
Les flux clavier et visuel utilisent aussi ces helpers pour rester coherents.
"""

# Regle axe -> (critere WCAG, niveau)
AXE_TO_WCAG = {
    "image-alt":            ("1.1.1", "A"),
    "input-image-alt":      ("1.1.1", "A"),
    "area-alt":             ("1.1.1", "A"),
    "color-contrast":       ("1.4.3", "AA"),
    "link-in-text-block":   ("1.4.1", "A"),
    "label":                ("1.3.1", "A"),
    "form-field-multiple-labels": ("1.3.1", "A"),
    "select-name":          ("4.1.2", "A"),
    "button-name":          ("4.1.2", "A"),
    "link-name":            ("2.4.4", "A"),
    "aria-required-attr":   ("4.1.2", "A"),
    "aria-roles":           ("4.1.2", "A"),
    "aria-valid-attr":      ("4.1.2", "A"),
    "aria-valid-attr-value": ("4.1.2", "A"),
    "aria-hidden-focus":    ("4.1.2", "A"),
    "heading-order":        ("1.3.1", "A"),
    "empty-heading":        ("1.3.1", "A"),
    "document-title":       ("2.4.2", "A"),
    "html-has-lang":        ("3.1.1", "A"),
    "html-lang-valid":      ("3.1.1", "A"),
    "duplicate-id":         ("4.1.1", "A"),
    "list":                 ("1.3.1", "A"),
    "listitem":             ("1.3.1", "A"),
    "tabindex":             ("2.4.3", "A"),
    "frame-title":          ("4.1.2", "A"),
    "meta-viewport":        ("1.4.4", "AA"),
}

# Libelles lisibles des criteres cites dans le projet.
WCAG_LABELS = {
    "1.1.1": "Contenu non textuel (alternatives textuelles)",
    "1.3.1": "Information et relations",
    "1.4.1": "Utilisation de la couleur",
    "1.4.3": "Contraste (minimum)",
    "1.4.4": "Redimensionnement du texte",
    "1.4.5": "Texte sous forme d'image",
    "2.1.1": "Clavier",
    "2.1.2": "Pas de piege au clavier",
    "2.4.2": "Titre de page",
    "2.4.3": "Parcours du focus",
    "2.4.4": "Fonction du lien (selon le contexte)",
    "2.4.7": "Visibilite du focus",
    "3.1.1": "Langue de la page",
    "4.1.1": "Analyse syntaxique",
    "4.1.2": "Nom, role et valeur",
}

DEFAULT = ("4.1.2", "A")   # repli si une regle inconnue apparait


def from_axe_rule(rule_id: str) -> tuple[str, str]:
    """Retourne (critere, niveau) pour un identifiant de regle axe."""
    return AXE_TO_WCAG.get(rule_id, DEFAULT)


def label(wcag: str) -> str:
    """Retourne le libelle lisible d'un critere, ou le critere seul si inconnu."""
    return WCAG_LABELS.get(wcag, "Critere WCAG")


def priority(level: str, severity: str) -> int:
    """
    Calcule une priorite numerique (plus petit = plus urgent) pour le tri.
    Combine le niveau WCAG (A avant AA) et la severite technique.
    """
    level_rank = {"A": 0, "AA": 1, "AAA": 2}.get(level, 3)
    sev_rank = {"critique": 0, "majeur": 1, "mineur": 2, "info": 3}.get(severity, 2)
    return level_rank * 10 + sev_rank


# --- Traductions FR des regles axe-core -------------------------------------
# axe-core renvoie ses messages en anglais. Pour un rapport 100 % francais, on
# fournit ici un titre + une description en francais par regle. from_axe_rule_fr
# retourne (titre_fr, description_fr) ; repli generique si la regle est inconnue.
AXE_RULE_FR = {
    "image-alt":        ("Image sans texte alternatif",
                         "Une image n'a pas de texte alternatif (attribut alt)."),
    "input-image-alt":  ("Bouton-image sans texte alternatif",
                         "Un bouton de type image n'a pas de texte alternatif."),
    "area-alt":         ("Zone cliquable sans texte alternatif",
                         "Une zone d'image reactive (area) n'a pas de texte alternatif."),
    "color-contrast":   ("Contraste de couleur insuffisant",
                         "Le contraste entre le texte et l'arriere-plan est sous le seuil WCAG AA."),
    "link-in-text-block": ("Lien distingue par la couleur seule",
                         "Un lien dans un bloc de texte n'est distingue que par la couleur."),
    "label":            ("Champ de formulaire sans etiquette",
                         "Un champ de formulaire n'a pas d'etiquette associee."),
    "form-field-multiple-labels": ("Champ avec plusieurs etiquettes",
                         "Un champ de formulaire a plusieurs etiquettes, source de confusion."),
    "select-name":      ("Liste deroulante sans nom accessible",
                         "Un element select n'a pas de nom accessible."),
    "button-name":      ("Bouton sans nom accessible",
                         "Un bouton n'a pas de texte ou de nom accessible."),
    "link-name":        ("Lien sans texte identifiable",
                         "Un lien n'a pas de texte permettant d'en identifier la fonction."),
    "aria-required-attr": ("Attribut ARIA requis manquant",
                         "Un attribut ARIA obligatoire est absent."),
    "aria-roles":       ("Role ARIA invalide",
                         "Un role ARIA utilise n'est pas valide."),
    "aria-valid-attr":  ("Attribut ARIA invalide",
                         "Un attribut ARIA utilise n'est pas valide."),
    "aria-valid-attr-value": ("Valeur d'attribut ARIA invalide",
                         "La valeur d'un attribut ARIA n'est pas valide."),
    "aria-hidden-focus": ("Element masque mais focusable",
                         "Un element cache aux lecteurs d'ecran (aria-hidden) reste atteignable au clavier."),
    "heading-order":    ("Ordre des titres incorrect",
                         "La hierarchie des titres (h1, h2...) n'est pas respectee."),
    "empty-heading":    ("Titre vide",
                         "Un element de titre ne contient aucun texte."),
    "document-title":   ("Titre de page manquant",
                         "La page n'a pas de titre (element title)."),
    "html-has-lang":    ("Langue de la page non declaree",
                         "L'element html n'a pas d'attribut lang indiquant la langue."),
    "html-lang-valid":  ("Langue de la page invalide",
                         "L'attribut lang de la page n'a pas une valeur valide."),
    "duplicate-id":     ("Identifiant duplique",
                         "Un meme identifiant (id) est utilise plusieurs fois."),
    "list":             ("Liste mal structuree",
                         "Une liste n'est pas structuree correctement."),
    "listitem":         ("Element de liste hors liste",
                         "Un element de liste (li) n'est pas dans une liste valide."),
    "tabindex":         ("Ordre de tabulation force",
                         "Un tabindex positif force un ordre de tabulation non naturel."),
    "frame-title":      ("Cadre sans titre",
                         "Un cadre (iframe) n'a pas de titre descriptif."),
    "meta-viewport":    ("Zoom desactive",
                         "La balise meta viewport empeche le zoom et l'agrandissement du texte."),
    "definition-list":  ("Liste de definitions mal structuree",
                         "Un element dl ne contient pas correctement des groupes dt/dd."),
}

DEFAULT_RULE_FR = ("Probleme d'accessibilite detecte",
                   "Une regle d'accessibilite n'est pas respectee.")


def from_axe_rule_fr(rule_id: str) -> tuple[str, str]:
    """Retourne (titre_fr, description_fr) pour un identifiant de regle axe."""
    return AXE_RULE_FR.get(rule_id, DEFAULT_RULE_FR)
