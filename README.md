# Agent d'accessibilité « libre de droits »

Agent de test d'accessibilité web (WCAG), 100 % local et libre de droits, conçu dans le cadre du cours MGL805 (Équipe 6). Il combine trois flux d'analyse complémentaires et produit un rapport Markdown + HTML.

- **Flux code** : axe-core injecté dans le DOM. Analyse statique, déterministe.
- **Flux clavier** : test comportemental réel (focus, piège clavier, modale). Dynamique.
- **Flux visuel (IA)** : Qwen2.5-VL en local via Ollama. Jugement perceptuel.

---

## 1. Prérequis

- **Python 3.10 ou plus.** La dépendance `jsonschema` 4.26 exige Python ≥ 3.10 ; une version antérieure (3.9 ou moins) fait échouer `pip install`. Vérifiez avec :
  ```
  python --version
  ```
- **Ollama** installé, avec le modèle `qwen2.5vl:7b`, pour le flux visuel. En son absence, l'agent le signale et produit quand même le rapport des flux code et clavier.
- Un GPU est recommandé pour le flux visuel (NVIDIA ou Intel Arc), mais le CPU fonctionne aussi, plus lentement.

---

## 2. Installation

> Ne copiez jamais le dossier `.venv/` d'une machine à l'autre : il se recrée localement.

### Windows (PowerShell)
```
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

### macOS / Linux
```
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

### Modèle de vision (Ollama)
```
ollama pull qwen2.5vl:7b
```
Lancez ensuite le serveur Ollama (`ollama serve`, ou le script de lancement fourni) avant d'utiliser le flux visuel.

### Dépendances
Le projet a quatre dépendances, toutes multiplateformes (voir `requirements.txt`) : `playwright` (navigateur), `requests` (appels Ollama et API commerciales), `Pillow` (traitement et découpage d'image), `jsonschema` (validation des constats). Les API Claude et Gemini sont appelées via `requests` : aucun SDK supplémentaire.

Pour vérifier que tout est bien installé dans l'environnement actif :
```
python -c "import jsonschema, PIL, requests, playwright; print('OK')"
```

---

## 3. Utilisation

### Cas simple (ordinateur normal)
Aucune variable d'environnement n'est nécessaire : les valeurs par défaut conviennent sur toute machine (Intel ou NVIDIA). Le découpage par défaut (`SAFE_SMALL`) garde les tuiles lisibles, y compris sur les pages longues.

```
# Auditer une page de test locale
python run.py "test_page/index.html"

# Auditer un site en ligne
python run.py "https://www.w3.org/WAI/demos/bad/before/home.html"
```

Le rapport est généré dans `output/` :
- un rapport horodaté `AAAA-MM-JJ-HH-MM-SS.html` / `.md` / `.json` (un par cible) ;
- plus les noms fixes `rapport.html` / `rapport.md` / `findings.json` (dernier run).

Le rapport HTML est autonome : la capture (ou la tuile) analysée par le flux visuel est intégrée sous chaque constat.

### Plusieurs cibles à la fois
`run.py` accepte plusieurs arguments (URLs, fichiers, images), un dossier ou un motif glob. Chaque cible produit son propre rapport horodaté ; une cible qui échoue n'arrête pas les autres.
```
python run.py "https://a.com" "https://b.com" "test_page/index.html"
python run.py "test_page/*"
python run.py test_page/
```

### Analyser une image statique
Si la cible est une image (`.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.gif`), l'agent lance uniquement le flux visuel (pas de DOM, donc ni flux code ni flux clavier) :
```
python run.py "capture.png"
```

### Sans le flux visuel (par exemple sans Ollama)
```
python run.py "https://exemple.com" --no-visual
```

---

## 4. Variables d'environnement

Toutes optionnelles. Les défauts conviennent à un usage normal.

| Variable | Valeurs | Défaut | Effet |
|---|---|---|---|
| `VISION_BACKEND` | `ollama` / `claude` / `gemini` | `ollama` | Choisit le modèle qui analyse l'image : local libre de droits, ou API commerciale pour comparer. |
| `AGENT_TILING` | `OFF` / `SAFE_SMALL` / `IGPU_SYCL` | `SAFE_SMALL` | Faut-il découper la page ? `SAFE_SMALL` (défaut) = tuiles ≤ 756 px, convient aux pages courtes comme longues ; `OFF` = une seule image (voir note ci-dessous) ; `IGPU_SYCL` = tuiles ≤ 1008 px. |
| `TILING_STRATEGY` | `SEQ` / `LOT` / `LOT_VUE` / `LOT_ANCRAGE` | `SEQ` | Comment présenter les tuiles au modèle (voir section 5). Sans effet si `AGENT_TILING=OFF`. |
| `HEADLESS` | `True` / `False` | `True` | Navigateur sans fenêtre (adapté à la CI) ou visible (démo, débogage). |
| `AGENT_DEBUG` | `0` / `1` | `0` | À `1`, affiche le prompt envoyé au modèle et sa réponse brute. |
| `ANTHROPIC_API_KEY` | clé `sk-ant-...` | (vide) | Requise si `VISION_BACKEND=claude`. Jamais en dur dans le code. |
| `GEMINI_API_KEY` | clé `AIza...` | (vide) | Requise si `VISION_BACKEND=gemini`. Jamais en dur dans le code. |

### Les poser (PowerShell, Windows)
```
$env:AGENT_TILING = "SAFE_SMALL"
$env:TILING_STRATEGY = "SEQ"
python run.py "test_page/index.html"
```

### Les poser (bash / CI, Linux ou macOS)
```
AGENT_TILING=SAFE_SMALL TILING_STRATEGY=SEQ python run.py "test_page/index.html"
```

### Revenir aux défauts (PowerShell)
```
Remove-Item Env:AGENT_TILING, Env:TILING_STRATEGY
```

### Autres pages testés
```
$env:AGENT_TILING = "SAFE_SMALL"
$env:TILING_STRATEGY = "SEQ"
python run.py "test_page/index.html" "test_page/index_long.html" "https://www.w3.org/WAI/demos/bad/before/home.html" 
```
---

## 5. Comprendre le découpage et les stratégies

Le flux visuel doit composer avec deux contraintes : la taille d'image que le matériel peut traiter, et la lisibilité d'une page plus haute qu'un écran. Deux réglages répondent à cela.

### `AGENT_TILING` : faut-il découper ?
- `SAFE_SMALL` (défaut, tuiles ≤ 756 px) : découpe la page en carrés lisibles. Convient aux pages courtes comme longues, sur toute machine (Intel ou NVIDIA).
- `OFF` : envoie la page entière au modèle en une seule image. Sur une page courte, c'est plus rapide et l'image reste lisible. Sur une page longue, l'image est réduite à 768 px et devient illisible : le flux visuel ne détecte alors rien. Cette réduction a lieu sur toute machine, y compris NVIDIA (elle n'est pas liée au crash matériel propre à l'Intel Arc). À réserver aux pages courtes et aux images statiques.
- `IGPU_SYCL` (tuiles ≤ 1008 px) : limite haute sur GPU Intel Arc. Peut provoquer un crash SYCL sur certains matériels ; utiliser `SAFE_SMALL` en repli.

Le découpage se fait en carrés pleine largeur, à l'échelle d'un écran (pas en petites zones), avec une marge de chevauchement : une même bande apparaît dans deux tuiles consécutives, pour qu'aucun élément ne soit tranché à la frontière.

### `TILING_STRATEGY` : comment présenter les tuiles au modèle
Ne s'applique que si `AGENT_TILING` n'est pas `OFF`.

| Stratégie | Principe | État |
|---|---|---|
| `SEQ` (défaut) | Une tuile par appel, en boucle, puis agrégation. | Validée. Seule stratégie fiable sur le modèle 7B local. |
| `LOT` | Toutes les tuiles en un seul appel. | Échoue sur le 7B : le multi-images n'est pas géré. Conservée pour la V2. |
| `LOT_VUE` | `LOT` + une vue d'ensemble réduite. | Même limite. Conservée pour la V2. |
| `LOT_ANCRAGE` | `LOT_VUE` + position de chaque tuile dans le prompt. | Même limite, et dégrade. Conservée pour la V2. |

Résultat mesuré : sur le 7B local, la variable déterminante est le nombre d'images par appel, pas leur contenu. Une seule image par appel (`SEQ`) fonctionne ; plusieurs images en un appel (`LOT*`) échouent. Les variantes `LOT*` restent dans le code car elles pourraient devenir viables sur un modèle plus puissant.

Le guide [GUIDE_TEST_TUILAGE.md](GUIDE_TEST_TUILAGE.md) donne des commandes de test prêtes à l'emploi.

---

## 6. Mode headless (`HEADLESS=True`)

En mode headless (le défaut), Playwright utilise un binaire séparé, `chromium-headless-shell` :
```
python -m playwright install chromium-headless-shell
```
Si un antivirus intercepte le HTTPS (erreur `SELF_SIGNED_CERT_IN_CHAIN`), contournez le temps de l'installation :
```
$env:NODE_TLS_REJECT_UNAUTHORIZED = "0"
python -m playwright install chromium-headless-shell
Remove-Item Env:NODE_TLS_REJECT_UNAUTHORIZED
```
Si vous ne pouvez pas l'installer, lancez en fenêtre visible : `$env:HEADLESS = "False"`.

---

## 7. Comparer le modèle local à un modèle commercial

Le mode local reste le défaut. Les backends commerciaux servent uniquement à produire des données de comparaison (mêmes pages, même protocole).

```
# Gemini (palier gratuit, clé via Google AI Studio)
$env:VISION_BACKEND = "gemini"
$env:GEMINI_API_KEY = "AIza..."
python run.py "test_page/index.html"

# Claude (API payante, crédit requis)
$env:VISION_BACKEND = "claude"
$env:ANTHROPIC_API_KEY = "sk-ant-..."
python run.py "test_page/index.html"
```

Chaque exécution ajoute une ligne au journal `output/execution_log.csv` : date-heure de début et de fin, durée, cible, backend, modèle, tuilage, stratégie, nombre de constats. Un abonnement « Pro » (Claude ou Gemini) ne donne pas d'accès API ; la clé se crée sur la console développeur du fournisseur.

---

## 8. Sorties

Dans `output/` :
- `AAAA-MM-JJ-HH-MM-SS.html` : rapport HTML autonome (image analysée sous chaque constat visuel).
- `AAAA-MM-JJ-HH-MM-SS.md` et `.json` : mêmes constats en Markdown et en JSON.
- `rapport.html` / `rapport.md` / `findings.json` : copies du dernier run.
- `execution_log.csv` : journal des exécutions (une ligne par cible).
- `tiles/` : images analysées (tuiles ou capture unique selon le mode).
