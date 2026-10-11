# Guide de test — découpage & stratégies du flux visuel

Ce guide permet d'**activer/désactiver** le découpage d'images et de **comparer**
les stratégies d'analyse du flux visuel.

Tout se pilote par **deux variables d'environnement**, sans toucher au code.

---

## Les deux réglages

### 1. Option « mère » — `AGENT_TILING` : *faut-il découper ?*

| Valeur | Effet | Quand l'utiliser |
|---|---|---|
| `OFF` *(défaut)* | Pas de découpage. Une seule image (réduite si trop grande). | CPU, NVIDIA, ou pages courtes. |
| `IGPU_SYCL` | Découpe en tuiles de **1008 px** max. | **iGPU Intel Arc** (contourne le crash SYCL) ; aussi utile pour les pages longues sur tout matériel. |
| `SAFE_SMALL` | Découpe en tuiles de **756 px** max. | Repli si 1008 pose encore problème. |

> Le découpage a **deux justifications** : éviter le *crash SYCL* (spécifique Intel)
> **et** garder une page longue *lisible* (universel, tout matériel).

### 2. Option « fille » — `TILING_STRATEGY` : *comment recoller ?*

**Ne s'applique QUE si `AGENT_TILING` ≠ `OFF`.**

| Valeur | Ce qu'on envoie au modèle | Statut |
|---|---|---|
| `SEQ` *(défaut)* | **Une tuile par appel**, en boucle, puis agrégation. | ✅ **Validé** — seule stratégie qui fonctionne sur le 7B. |
| `LOT` | Toutes les tuiles en **un seul appel**. | ❌ Échoue sur le 7B (multi-images). Conservé pour la V2. |
| `LOT_VUE` | `LOT` **+** une vue d'ensemble réduite (contexte). | ❌ Même limite multi-images. Conservé pour la V2. |
| `LOT_ANCRAGE` | `LOT_VUE` **+** la position (x,y) de chaque tuile dans le prompt. | ❌ Même limite, et dégrade (hallucinations). Conservé pour la V2. |

> **Résultat mesuré :** le modèle 7B local ne gère pas plusieurs images dans un
> même appel. Seul `SEQ` (une image à la fois) fonctionne. Les variantes `LOT*`
> sont conservées dans le code car elles pourraient devenir viables sur un modèle
> plus puissant (72B, cloud, fine-tuné) — à réévaluer en V2.

---

## Commandes de test (Windows CMD)

> Prérequis : le serveur Ollama (Intel) tourne déjà (`start-ollama.bat`).
> Les variables se posent **dans la fenêtre où vous lancez `python run.py`**.

### Cas par défaut — pas de découpage (une seule image)
```
python run.py
```
> Équivaut à `AGENT_TILING=OFF`. C'est le comportement de base.

### Découpage activé, stratégie SEQ (recommandée — iGPU Intel / pages longues)
```
set AGENT_TILING=SAFE_SMALL
set TILING_STRATEGY=SEQ
python run.py
```

### Comparer avec les stratégies multi-images (LOT) — pour la V2
```
set AGENT_TILING=SAFE_SMALL
set TILING_STRATEGY=LOT          REM ou LOT_VUE / LOT_ANCRAGE
python run.py
```
> Note : les LOT* échouent sur le 7B (multi-images). Utiles seulement pour
> comparer / documenter, ou tester un modèle plus puissant.

### Revenir au défaut (désactiver le découpage) dans la même fenêtre
```
set AGENT_TILING=
set TILING_STRATEGY=
python run.py
```
> Vider la variable la ramène à sa valeur par défaut (`OFF` / `SEQ`).

### Sauter complètement le flux visuel (test rapide sans le modèle)
```
python run.py --no-visual
```

---

## PowerShell (si vous préférez)

```powershell
$env:AGENT_TILING = "SAFE_SMALL"
$env:TILING_STRATEGY = "SEQ"
python run.py

# revenir au defaut :
Remove-Item Env:AGENT_TILING, Env:TILING_STRATEGY
```

---

## Protocole de comparaison suggéré (pour le rapport, chapitre 6)

1. Lancez la **même page** avec `A`, puis `B`, puis `C`.
2. Comparez, pour chaque, le fichier `output/rapport.md` :
   - nombre de constats perceptuels trouvés,
   - exactitude (vrais défauts vs hallucinations),
   - temps d'exécution affiché.
3. Notez laquelle donne le meilleur compromis **précision / temps**.

> Astuce : renommez `output/rapport.md` entre chaque essai
> (ex. `rapport_A.md`, `rapport_B.md`, `rapport_C.md`) pour les garder côte à côte.

---

## Rappel des réglages serveur (dans `ollama-serve.bat`)

Ces variables-là concernent le **serveur Ollama**, pas l'agent :
```bat
set OLLAMA_CONTEXT_LENGTH=8192
set OLLAMA_NUM_PARALLEL=1
set OLLAMA_MODELS=C:\Users\thier\.ollama\models
```
