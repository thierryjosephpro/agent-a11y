# Agent d'accessibilité « libre de droits »

Agent de test d'accessibilité web (WCAG), **100 % local et libre de droits**, conçu dans le cadre du cours MGL805 (Équipe 6). Il combine trois flux d'analyse complémentaires et produit un rapport Markdown + HTML.

- **Flux code** — axe-core injecté dans le DOM (déterministe).
- **Flux clavier** — test comportemental réel (focus, piège clavier, modale).
- **Flux visuel (IA)** — Qwen2.5-VL en local via Ollama (défauts perceptuels).

---

## 1. Installation

> Ne copiez jamais le dossier `.venv/` d'une machine à l'autre : il se recrée localement.

### Windows (PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

Le **flux visuel** nécessite un serveur **Ollama** lancé avec le modèle `qwen2.5vl:7b`
(voir les scripts de lancement fournis). Si Ollama n'est pas lancé, l'agent le
signale clairement et produit quand même le rapport des flux code + clavier.

---

## 2. Utilisation

### Cas simple (utilisateur normal)
Aucune variable d'environnement n'est nécessaire — les valeurs par défaut conviennent :

```powershell
# Auditer un site
python run.py "https://exemple.com"

# Auditer une page locale
python run.py "test_page/index.html"
```

Le rapport est généré dans `output/` :
- un rapport **horodaté** `AAAA-MM-JJ-HH-MM-SS.html` / `.md` / `.json` (un par cible) ;
- plus les noms fixes `rapport.html` / `rapport.md` / `findings.json` (dernier run).

### Plusieurs cibles à la fois
`run.py` accepte **plusieurs arguments** (URLs, fichiers, images), un **dossier**, ou un **motif glob**. Chaque cible produit son propre rapport horodaté.

```powershell
# Plusieurs URLs / fichiers
python run.py "https://a.com" "https://b.com" "test_page/index.html"

# Toutes les pages d'un dossier (glob)
python run.py "test_page/*"

# Tout le contenu d'un dossier
python run.py test_page/
```

### Analyser une image statique
Si la cible est une **image** (`.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.gif`),
l'agent lance **uniquement le flux visuel** (il n'y a pas de DOM, donc ni flux
code ni flux clavier) :

```powershell
python run.py "capture.png"
```

### Sans le flux visuel (ex. sans Ollama)
```powershell
python run.py "https://exemple.com" --no-visual
```

---

## 3. Variables d'environnement

Toutes optionnelles. Les défauts conviennent à un usage normal.

| Variable | Valeurs | Défaut | Effet |
|---|---|---|---|
| `HEADLESS` | `True` / `False` | **`True`** | Navigateur sans fenêtre. `True` = adapté à la CI (GitLab/GitHub). `False` = fenêtre visible (démo, débogage). |
| `AGENT_DEBUG` | `0` / `1` | **`0`** | À `1`, affiche le prompt envoyé au modèle **et** sa réponse brute. À laisser à `0` en usage normal. |
| `AGENT_TILING` | `OFF` / `SAFE_SMALL` / `IGPU_SYCL` | **`OFF`** | `OFF` = une seule image ; `SAFE_SMALL` = découpe en morceaux ≤ 756 px (iGPU Intel / pages longues) ; `IGPU_SYCL` = 1008 px (⚠️ peut crasher sur certains iGPU Intel). |
| `TILING_STRATEGY` | `SEQ` / `LOT` / `LOT_VUE` / `LOT_ANCRAGE` | **`SEQ`** | `SEQ` = une tuile par appel (seule stratégie validée) ; `LOT*` = plusieurs images en un appel (échouent sur le 7B, conservées pour la V2). |

### Les poser (PowerShell — Windows)
```powershell
$env:AGENT_DEBUG = "1"
$env:AGENT_TILING = "SAFE_SMALL"
$env:TILING_STRATEGY = "SEQ"
python run.py "https://exemple.com"
```

### Les poser (bash / CI — macOS / Linux)
```bash
AGENT_DEBUG=1 AGENT_TILING=SAFE_SMALL TILING_STRATEGY=SEQ python run.py "https://exemple.com"
```

### Repartir des défauts (PowerShell)
Les variables « collent » dans une session PowerShell. Pour les effacer :
```powershell
Remove-Item Env:AGENT_DEBUG, Env:AGENT_TILING, Env:TILING_STRATEGY, Env:HEADLESS
```

---

## 4. Exécuter en mode headless (`HEADLESS=True`)

En mode headless, Playwright utilise un binaire séparé : **chromium-headless-shell**.
S'il n'est pas installé, l'agent échoue au lancement du navigateur.

```powershell
python -m playwright install chromium-headless-shell
```

> **Réseau d'entreprise / antivirus interceptant le HTTPS (ex. Kaspersky).**
> Le téléchargement peut échouer avec `SELF_SIGNED_CERT_IN_CHAIN`. Contournement
> ponctuel (à ne garder que le temps de l'installation) :
> ```powershell
> $env:NODE_TLS_REJECT_UNAUTHORIZED = "0"
> python -m playwright install chromium-headless-shell
> Remove-Item Env:NODE_TLS_REJECT_UNAUTHORIZED
> ```
> Alternative plus propre : fournir le certificat racine de l'entreprise via
> `NODE_EXTRA_CA_CERTS` pointant vers le fichier `.pem`.

Si vous ne pouvez pas installer le headless-shell, lancez en fenêtre visible :
```powershell
$env:HEADLESS = "False"
python run.py "https://exemple.com"
```

---

## 5. Pourquoi « hybride » ?

L'agent est dit **hybride** parce qu'il combine des méthodes de détection de
natures différentes, chacune adaptée à une famille de barrières d'accessibilité :

1. **Déterministe par le code** (axe-core) — ce qui est décidable mécaniquement
   dans le HTML/DOM : contrastes, textes alternatifs, étiquettes, ARIA, langue.
   Fiable et reproductible.
2. **Comportemental** (test clavier réel) — ce qui ne se voit ni dans le code ni
   sur une image fixe : ordre et visibilité du focus, piège clavier, fermeture
   de modale. Nécessite d'*interagir* avec la page.
3. **Perceptuel par l'IA** (modèle vision-langage local) — ce qui se juge « à
   l'œil » : information portée par la seule couleur, texte intégré dans une
   image, hiérarchie visuelle trompeuse.

Aucune de ces méthodes seule ne couvre l'accessibilité : les outils
déterministes ratent le comportemental et le perceptuel ; l'IA seule n'est ni
fiable ni reproductible. L'agent est donc **hybride** : il oriente chaque type de
barrière vers la méthode la mieux adaptée, puis agrège les résultats. Les flux
déterministes forment le socle fiable ; le flux visuel est un **complément** dont
les constats sont à valider.

---

## 6. Sorties

Dans `output/` :
- `AAAA-MM-JJ-HH-MM-SS.html` — rapport HTML autonome (une tuile affichée sous
  chaque constat du flux visuel).
- `AAAA-MM-JJ-HH-MM-SS.md` — rapport Markdown.
- `AAAA-MM-JJ-HH-MM-SS.json` — constats bruts.
- `rapport.html` / `rapport.md` / `findings.json` — copies du **dernier** run.
- `capture.png` — capture de la page.
- `tiles/` — tuiles générées (mode découpage).
