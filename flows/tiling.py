"""
Decoupage d'images en tuiles a resolution native (pour le flux visuel).

Pourquoi : une capture de page longue ne peut pas etre analysee en une seule
image (crash SYCL sur iGPU Intel si une dimension > ~1024 ; illisibilite sur
tout materiel si on l'ecrase). On la decoupe donc en tuiles dont chaque
dimension reste sous la limite, SANS redimensionner (crops natifs = zero perte).

Principes (valides avec l'utilisateur) :
- decoupage sur les DEUX axes des qu'une dimension depasse la taille de tuile ;
- les tuiles de bord ("restes") sont plus petites, c'est normal et voulu ;
- un CHEVAUCHEMENT (overlap) evite de couper un element pile sur une frontiere ;
- un reste plus fin que TILE_MIN_REMAINDER est ignore (bande inexploitable).

Ce module ne fait que produire des tuiles + leurs coordonnees. Il ne parle pas
au modele : c'est flow_visual.py qui decide quoi en faire (strategies A/B/C).
"""

import base64
import io
from dataclasses import dataclass

from PIL import Image

import config


@dataclass
class Tile:
    """Une tuile : l'image + sa position (col, row) et sa boite dans l'original."""
    image: Image.Image
    col: int          # index de colonne (0 = gauche)
    row: int          # index de ligne (0 = haut)
    box: tuple        # (left, top, right, bottom) en px dans l'image d'origine
    filename: str = None  # nom de fichier reel, pose par save_tiles (rattachement HTML)

    def to_base64(self, fmt: str = "PNG") -> str:
        buf = io.BytesIO()
        self.image.save(buf, format=fmt)
        return base64.b64encode(buf.getvalue()).decode("utf-8")


def _starts(total: int, tile: int, overlap: int, min_remainder: int) -> list[int]:
    """Positions de depart des tuiles sur un axe, avec chevauchement.

    Chaque tuile couvre [start, start+tile). On avance de (tile - overlap).
    Le dernier reste, s'il est plus fin que min_remainder, est absorbe par la
    tuile precedente (on ne cree pas de bande inutile).
    """
    if total <= tile:
        return [0]
    step = max(1, tile - overlap)
    starts = list(range(0, total - tile + 1, step))
    # gerer le reste final
    last_covered = starts[-1] + tile
    remainder = total - last_covered
    if remainder > min_remainder:
        starts.append(total - tile)   # une derniere tuile calee sur le bord droit/bas
    return starts


def split_image(img: Image.Image, tile_size: int,
                overlap: int = None, min_remainder: int = None) -> list[Tile]:
    """Decoupe une image PIL en tuiles de <= tile_size px (crops natifs).

    Retourne une liste de Tile, dans l'ordre lecture (haut->bas, gauche->droite).
    """
    overlap = config.TILE_OVERLAP if overlap is None else overlap
    min_remainder = config.TILE_MIN_REMAINDER if min_remainder is None else min_remainder

    w, h = img.size
    xs = _starts(w, tile_size, overlap, min_remainder)
    ys = _starts(h, tile_size, overlap, min_remainder)

    tiles = []
    for row, y in enumerate(ys):
        for col, x in enumerate(xs):
            right = min(x + tile_size, w)
            bottom = min(y + tile_size, h)
            box = (x, y, right, bottom)
            tiles.append(Tile(image=img.crop(box), col=col, row=row, box=box))
    return tiles


def downscale_overview(img: Image.Image, max_dim: int) -> Image.Image:
    """Reduit l'image entiere pour que sa plus grande dimension = max_dim.

    Sert a produire une "vue d'ensemble" (contexte) pour les strategies B/C.
    Le flou est assume : cette image sert au reperage, pas a la lecture.
    """
    w, h = img.size
    scale = min(1.0, max_dim / max(w, h))
    if scale >= 1.0:
        return img.copy()
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return img.resize(new_size, Image.LANCZOS)


def image_to_base64(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def needs_tiling(img: Image.Image, tile_size: int) -> bool:
    """Vrai si au moins une dimension depasse la taille de tuile."""
    w, h = img.size
    return w > tile_size or h > tile_size


def save_single_image(img, out_dir, name="image_analysee.png"):
    """Sauvegarde l'UNIQUE image envoyee au modele (mode OFF ou page courte).

    Nettoie le dossier puis ecrit l'image sous `name`, afin que le rapport HTML
    puisse l'afficher sous les constats, comme il le fait pour les tuiles.
    Retourne le nom de fichier.
    """
    import shutil
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    img.save(out_dir / name)
    print(f"  [visuel] image analysee enregistree dans {out_dir / name}")
    return name


def tile_filename(index, tile):
    """Nom de fichier canonique d'une tuile : tuile_{index:02d}_r{row}_c{col}.png.

    index est la position 0-base dans la liste passee a save_tiles. C'est la
    SEULE source de verite du nom : flow_visual.py le recupere via l'attribut
    .filename pose par save_tiles, il ne le reconstruit jamais a la main.
    """
    return f"tuile_{index:02d}_r{tile.row}_c{tile.col}.png"


def save_tiles(tiles, out_dir, overview=None):
    """Sauvegarde les tuiles (et la vue d'ensemble) sur disque.

    Nettoie d'abord le dossier pour ne pas melanger avec un run precedent.
    Pose sur CHAQUE tuile un attribut .filename (son nom de fichier reel), puis
    retourne la liste de ces noms, dans l'ordre. Le rattachement tuile->constat
    (rapport HTML) doit lire t.filename, jamais reconstruire le nom : c'est ce
    qui garantit l'alignement sur toute machine (Windows C:/ ou D:/, Linux CI).
    Retourne : liste des noms de fichiers (str), index-alignee avec `tiles`.
    """
    import shutil
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    if overview is not None:
        overview.save(out_dir / "vue_ensemble.png")
    names = []
    for i, t in enumerate(tiles):
        name = tile_filename(i, t)
        t.filename = name          # source de verite portee par la tuile
        t.image.save(out_dir / name)
        names.append(name)
    print(f"  [visuel] {len(tiles)} tuile(s)"
          f"{' + vue d ensemble' if overview is not None else ''} "
          f"enregistree(s) dans {out_dir}")
    return names


def tile_uniformity(img):
    """Analyse l'uniformite d'une image PIL.
    Retourne (ratio_couleur_dominante, couleur_dominante_rgb).
    ratio proche de 1.0 = tuile quasi unie. Echantillonne pour rester rapide.
    """
    small = img.convert("RGB")
    # sous-echantillonnage pour la vitesse (max ~64x64 points)
    w, h = small.size
    step = max(1, min(w, h) // 64)
    pixels = list(small.resize((max(1, w // step), max(1, h // step))).getdata())
    if not pixels:
        return 1.0, (255, 255, 255)
    # quantification grossiere (par pas de 16) pour tolerer le bruit JPEG/anti-alias
    def q(c):
        return (c[0] // 16, c[1] // 16, c[2] // 16)
    from collections import Counter
    counts = Counter(q(p) for p in pixels)
    (qr, qg, qb), top = counts.most_common(1)[0]
    ratio = top / len(pixels)
    dominant = (qr * 16, qg * 16, qb * 16)
    return ratio, dominant
def detect_background_color(img):
    """Estime la couleur de fond de la page en echantillonnant les 4 coins."""
    small = img.convert("RGB")
    w, h = small.size
    corners = [(2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)]
    from collections import Counter
    def q(c):
        return (c[0] // 16, c[1] // 16, c[2] // 16)
    vals = Counter(q(small.getpixel((x, y))) for x, y in corners)
    (qr, qg, qb), _ = vals.most_common(1)[0]
    return (qr * 16, qg * 16, qb * 16)
def color_distance(c1, c2):
    """Distance euclidienne simple entre deux couleurs RGB."""
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5
def color_name_fr(rgb):
    """Nom francais approximatif d'une couleur RGB, pour la description texte."""
    r, g, b = rgb
    if max(rgb) - min(rgb) < 25:
        if r > 200: return "blanc"
        if r < 60: return "noir"
        return "gris"
    if r > g and r > b: return "rouge" if g < 120 else "orange"
    if g > r and g > b: return "vert"
    if b > r and b > g: return "bleu"
    if r > 150 and g > 150: return "jaune"
    if g > 150 and b > 150: return "turquoise"
    return "couleur vive"


def split_into_squares(img, safe_size):
    """Decoupe la page en CARRES de la largeur de page, puis reduit a safe_size.
    Contrairement a split_image (grille largeur x hauteur), on ne coupe QU'EN
    HAUTEUR : chaque tuile fait toute la largeur de la page (aucune coupure
    verticale -> le contexte horizontal, ex. vert/rouge cote a cote, est
    preserve). Le cote du carre = largeur de la page ; la derniere tuile est
    plus courte (le reste). Chaque tuile est ensuite reduite pour que sa
    largeur = safe_size (meme facteur d'echelle qu'un ecran normal reduit).
    Retourne une liste de Tile (col toujours 0).
    """
    w, h = img.size
    side = w  # cote du carre = largeur de la page
    overlap = config.TILE_OVERLAP
    min_remainder = config.TILE_MIN_REMAINDER
    ys = _starts(h, side, overlap, min_remainder)
    tiles = []
    for row, y in enumerate(ys):
        bottom = min(y + side, h)
        box = (0, y, w, bottom)
        crop = img.crop(box)
        # reduction : largeur -> safe_size (hauteur suit le meme facteur)
        if w > safe_size:
            scale = safe_size / w
            new_size = (safe_size, max(1, int(crop.size[1] * scale)))
            crop = crop.resize(new_size, Image.LANCZOS)
        tiles.append(Tile(image=crop, col=0, row=row, box=box))
    return tiles

