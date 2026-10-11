"""
Flux "clavier" : test comportemental reel.

C'est le seul flux qui manipule vraiment l'interface au clavier. Il revele des
defauts invisibles au code ET a l'image :
  - ordre et visibilite du focus (2.4.3, 2.4.7),
  - piege clavier (2.1.2),
  - element non atteignable au clavier (2.1.1),
  - modale qui ne se ferme pas avec Echap / focus non deplace (2.1.2, 2.4.3).

C'est aussi ce flux qui declenche l'INTERACTION revelant le defaut
post-interaction de la page de test (ouverture de la modale).
"""

import config
from schemas import clean_findings

# Script JS : renvoie une signature de l'element actuellement focalise +
# une heuristique de visibilite du focus (outline / box-shadow).
_ACTIVE_ELEMENT_JS = """
() => {
    const el = document.activeElement;
    if (!el || el === document.body) return null;
    const cs = getComputedStyle(el);
    const hasOutline = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0;
    const hasShadow = cs.boxShadow && cs.boxShadow !== 'none';
    const rect = el.getBoundingClientRect();
    return {
        tag: el.tagName.toLowerCase(),
        id: el.id || '',
        text: (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 40),
        focusVisible: hasOutline || hasShadow,
        visible: rect.width > 0 && rect.height > 0,
        signature: el.tagName + '#' + (el.id || '') + '.' + (el.className || '')
    };
}
"""


def _tab_traversal(page, state: str) -> list[dict]:
    """Parcourt la page avec Tab et detecte focus invisible + piege clavier."""
    findings = []
    seen_signatures = []
    stuck_count = 0
    last_signature = None

    for i in range(config.MAX_TAB_STOPS):
        page.keyboard.press("Tab")
        info = page.evaluate(_ACTIVE_ELEMENT_JS)
        if info is None:
            continue

        sig = info["signature"]

        # Focus non visible -> 2.4.7 (AA)
        if not info["focusVisible"]:
            findings.append({
                "source": "clavier",
                "wcag": "2.4.7",
                "level": "AA",
                "severity": "majeur",
                "title": "Focus clavier non visible",
                "description": (
                    f"L'element <{info['tag']}> "
                    f"'{info['text'] or info['id'] or 'sans libelle'}' recoit le focus "
                    "mais aucun indicateur visuel (outline/box-shadow) n'est detecte."
                ),
                "selector": f"#{info['id']}" if info["id"] else info["tag"],
                "state": state,
            })

        # Detection de piege clavier : le focus ne bouge plus.
        if sig == last_signature:
            stuck_count += 1
            if stuck_count >= 3:
                findings.append({
                    "source": "clavier",
                    "wcag": "2.1.2",
                    "level": "A",
                    "severity": "critique",
                    "title": "Piege clavier potentiel",
                    "description": (
                        f"Le focus reste bloque sur <{info['tag']}> "
                        f"'{info['text'] or info['id']}' apres plusieurs Tab : "
                        "l'utilisateur clavier ne peut pas en sortir."
                    ),
                    "selector": f"#{info['id']}" if info["id"] else info["tag"],
                    "state": state,
                })
                break
        else:
            stuck_count = 0
        last_signature = sig
        seen_signatures.append(sig)

    return findings


def _modal_test(page, state: str) -> list[dict]:
    """Ouvre la modale (interaction) et teste fermeture Echap + deplacement du focus."""
    findings = []
    trigger = config.MODAL_TRIGGER_SELECTOR
    modal = config.MODAL_SELECTOR
    if not trigger or not modal:
        return findings

    if page.locator(trigger).count() == 0:
        return findings  # pas de declencheur sur cette page

    print("[flux clavier] interaction : ouverture de la modale (etat post-interaction)...")
    page.locator(trigger).click()
    page.wait_for_timeout(400)

    modal_loc = page.locator(modal)
    if modal_loc.count() == 0 or not modal_loc.first.is_visible():
        return findings  # rien ne s'est ouvert

    post_state = "modale-ouverte"

    # 1) Le focus a-t-il ete deplace DANS la modale ? -> 2.4.3
    focus_in_modal = page.evaluate(
        """(sel) => {
            const m = document.querySelector(sel);
            return m ? m.contains(document.activeElement) : false;
        }""",
        modal,
    )
    if not focus_in_modal:
        findings.append({
            "source": "clavier",
            "wcag": "2.4.3",
            "level": "A",
            "severity": "majeur",
            "title": "Focus non deplace vers la modale",
            "description": (
                "Apres ouverture de la modale, le focus clavier reste sur la page "
                "en arriere-plan au lieu d'entrer dans la fenetre modale."
            ),
            "selector": modal,
            "state": post_state,
        })

    # 2) La modale se ferme-t-elle avec Echap ? -> 2.1.2
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    still_visible = modal_loc.first.is_visible()
    if still_visible:
        findings.append({
            "source": "clavier",
            "wcag": "2.1.2",
            "level": "A",
            "severity": "critique",
            "title": "Modale non fermable au clavier (Echap)",
            "description": (
                "La touche Echap ne ferme pas la modale : un utilisateur clavier "
                "peut se retrouver piege dans la fenetre modale."
            ),
            "selector": modal,
            "state": post_state,
        })

    return findings


def run(session, state: str = "initial") -> list[dict]:
    """Execute le parcours clavier complet."""
    print("[flux clavier] parcours Tab, focus et piege clavier...")
    page = session.page
    findings = _tab_traversal(page, state)
    findings += _modal_test(page, state)
    findings = clean_findings(findings, source="clavier")
    print(f"[flux clavier] {len(findings)} constat(s) retenu(s).")
    return findings
