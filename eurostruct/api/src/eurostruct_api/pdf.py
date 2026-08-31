"""Un écrivain PDF minimal, déterministe, sans aucune dépendance.

POURQUOI PAS UNE BIBLIOTHÈQUE
------------------------------
Trois raisons, dans cet ordre.

**Le déterminisme.** La clé d'un livrable dérive de son contenu : deux
compositions du même calcul doivent produire **les mêmes octets**. La plupart
des générateurs écrivent une date de création, un identifiant aléatoire, un
nom de producteur versionné — trois façons de faire changer l'empreinte sans
qu'aucun chiffre du document ne bouge. Ici, rien n'est daté et rien n'est
aléatoire : un document PDF produit deux fois est **identique au bit près**.

**La surface.** Une note de calcul est du texte mis en page. Elle n'a besoin ni
de moteur de rendu HTML, ni de gestion de polices, ni de rasterisation. Les
quatorze polices standard de PDF suffisent, et elles n'ont pas à être
embarquées.

**L'auditabilité.** Ce fichier fait quelques centaines de lignes qu'un
relecteur peut lire en entier. Un document opposable dix ans ne devrait pas
dépendre d'un arbre de dépendances qu'on ne relit jamais.

CE QUE CE MODULE NE FAIT PAS
------------------------------
Ni images, ni couleurs de fond, ni tableaux à bordures, ni césure, ni texte
justifié, ni polices embarquées, ni chiffrement, ni signature. Ce ne sont pas
des oublis : chacune de ces choses appellerait un lecteur pour être vérifiée,
et rien ici n'est ajouté sans être éprouvé.

AUCUN CARACTÈRE N'EST PERDU EN SILENCE
----------------------------------------
Les polices standard sont encodées en WinAnsi, qui ne porte pas le grec. Une
note de calcul en porte — ``μ``, ``ξ``, ``ε`` sont des grandeurs, pas des
ornements. Ils sont donc écrits avec la police **Symbol**, dans un segment
distinct. Un caractère qui n'a de place ni dans l'une ni dans l'autre fait
**lever** : un document qui perdrait ``ε`` sans le dire affirmerait autre chose
que le calcul.
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from typing import Final

__all__ = [
    "Bloc",
    "CaractereNonRepresentable",
    "Champs",
    "Paragraphe",
    "Tableau",
    "Titre",
    "composer_pdf",
]


class CaractereNonRepresentable(ValueError):
    """Un caractère qu'aucune des deux polices ne sait écrire.

    ON LÈVE PLUTÔT QUE DE SUBSTITUER. Un point d'interrogation à la place d'une
    lettre grecque transformerait ``ε_s`` en ``?_s`` sans que personne ne le
    remarque, et la note affirmerait alors autre chose que le calcul.
    """


#: A4 en points typographiques (1/72 pouce).
PAGE_L: Final[float] = 595.28
PAGE_H: Final[float] = 841.89
MARGE: Final[float] = 56.7          # 20 mm
INTERLIGNE: Final[float] = 1.35

HELVETICA: Final[str] = "F1"
HELVETICA_GRAS: Final[str] = "F2"
COURIER: Final[str] = "F3"
SYMBOLE: Final[str] = "F4"

#: LES LETTRES GRECQUES, VERS LES CODES DE LA POLICE `Symbol`. Ce n'est pas une
#: table de translittération: chaque entrée désigne le glyphe que le lecteur
#: affichera, et une lettre absente d'ici fait lever plutôt que disparaître.
_GREC: Final[dict[str, int]] = {
    "Α": 0x41, "Β": 0x42, "Γ": 0x47, "Δ": 0x44, "Ε": 0x45, "Ζ": 0x5A,
    "Η": 0x48, "Θ": 0x51, "Ι": 0x49, "Κ": 0x4B, "Λ": 0x4C, "Μ": 0x4D,
    "Ν": 0x4E, "Ξ": 0x58, "Ο": 0x4F, "Π": 0x50, "Ρ": 0x52, "Σ": 0x53,
    "Τ": 0x54, "Υ": 0x55, "Φ": 0x46, "Χ": 0x43, "Ψ": 0x59, "Ω": 0x57,
    "α": 0x61, "β": 0x62, "γ": 0x67, "δ": 0x64, "ε": 0x65, "ζ": 0x7A,
    "η": 0x68, "θ": 0x71, "ι": 0x69, "κ": 0x6B, "λ": 0x6C, "μ": 0x6D,
    "ν": 0x6E, "ξ": 0x78, "ο": 0x6F, "π": 0x70, "ρ": 0x72, "σ": 0x73,
    "τ": 0x74, "υ": 0x75, "φ": 0x66, "χ": 0x63, "ψ": 0x79, "ω": 0x77,
    # `µ` MICRO SIGN (U+00B5) existe en WinAnsi, mais on le range ici aussi:
    # un lecteur ne doit pas voir deux dessins differents pour la meme
    # grandeur selon l'octet qui a servi a l'ecrire.
    "µ": 0x6D,
    "≤": 0xA3, "≥": 0xB3, "≠": 0xB9, "×": 0xB4, "·": 0xD7, "∞": 0xA5,
    "√": 0xD6, "∅": 0xC6,
}

#: Ce que l'on remplace SANS PERTE DE SENS, parce que WinAnsi ne les porte pas
#: et qu'aucun glyphe Symbol ne leur correspond.
_EQUIVALENTS: Final[dict[str, str]] = {
    " ": " ",     # espace insecable -> espace
    " ": " ",     # espace fine insecable
    "‑": "-",     # trait d'union insecable
    "–": "-",     # tiret demi-cadratin
    "—": "--",    # tiret cadratin
    "‘": "'", "’": "'",
    "“": '"', "”": '"',
    "…": "...",
    "−": "-",     # signe moins
}


@dataclass(frozen=True)
class Titre:
    """Un intertitre. ``niveau`` 1 pour le titre du document, 2 pour une
    section."""

    texte: str
    niveau: int = 2


@dataclass(frozen=True)
class Paragraphe:
    """Du texte courant, replié à la largeur utile."""

    texte: str
    gras: bool = False
    #: Un encadré: le texte est precede d'un filet vertical. Sert au filigrane
    #: et a la mention obligatoire — ce qu'un lecteur ne doit pas manquer.
    encadre: bool = False


@dataclass(frozen=True)
class Champs:
    """Une liste « libellé : valeur »."""

    paires: list[tuple[str, str]]


@dataclass(frozen=True)
class Tableau:
    """Un tableau à colonnes fixes, sans bordure."""

    entetes: list[str]
    lignes: list[list[str]]
    #: Colonnes alignees a droite (indices).
    droite: set[int] = field(default_factory=set)


Bloc = Titre | Paragraphe | Champs | Tableau


# --------------------------------------------------------------- métrique
#: LARGEURS DES GLYPHES DES POLICES STANDARD, en millièmes de cadratin. Elles
#: sont dans la specification PDF et ne dependent d'aucun fichier de police:
#: c'est ce qui permet de replier le texte sans jamais lire une police.
_HELV = (
    "278 278 355 556 556 889 667 191 333 333 389 584 278 333 278 278 "
    "556 556 556 556 556 556 556 556 556 556 278 278 584 584 584 556 "
    "1015 667 667 722 722 667 611 778 722 278 500 667 556 833 722 778 "
    "667 778 722 667 611 722 667 944 667 667 611 278 278 278 469 556 "
    "333 556 556 500 556 556 278 556 556 222 222 500 222 833 556 556 "
    "556 556 333 500 278 556 500 722 500 500 500 334 260 334 584"
)
_HELV_GRAS = (
    "278 333 474 556 556 889 722 238 333 333 389 584 278 333 278 278 "
    "556 556 556 556 556 556 556 556 556 556 333 333 584 584 584 611 "
    "975 722 722 722 722 667 611 778 722 278 556 722 611 833 722 778 "
    "667 778 722 667 611 722 667 944 667 667 611 333 278 333 584 556 "
    "333 556 611 556 611 556 333 611 611 278 278 556 278 889 611 611 "
    "611 611 389 556 333 611 556 778 556 556 500 389 280 389 584"
)


def _table_largeurs(serie: str) -> dict[int, int]:
    """Associe chaque code WinAnsi 32..126 à sa largeur."""
    valeurs = [int(v) for v in serie.split()]
    return {32 + i: v for i, v in enumerate(valeurs)}


_LARGEURS: Final[dict[str, dict[int, int]]] = {
    HELVETICA: _table_largeurs(_HELV),
    HELVETICA_GRAS: _table_largeurs(_HELV_GRAS),
}
#: Courier est a chasse fixe: 600 pour tout. Symbol varie, mais les lettres
#: grecques employees ici tiennent toutes dans une largeur voisine de celle
#: d'une minuscule Helvetica; on prend 556, ce qui ne decale un repli que d'une
#: fraction de caractere et ne peut pas faire deborder une ligne.
_LARGEUR_COURIER: Final[int] = 600
_LARGEUR_SYMBOLE: Final[int] = 556


def _largeur(texte: str, police: str, corps: float) -> float:
    """La largeur d'un texte, en points."""
    if police == COURIER:
        return len(texte) * _LARGEUR_COURIER * corps / 1000.0
    table = _LARGEURS.get(police, _LARGEURS[HELVETICA])
    total = 0
    for caractere in texte:
        if caractere in _GREC:
            total += _LARGEUR_SYMBOLE
            continue
        octet = _winansi(caractere)
        total += table.get(octet, 556)
    return total * corps / 1000.0


def _winansi(caractere: str) -> int:
    """Le code WinAnsi d'un caractère, ou -1 s'il n'y en a pas."""
    try:
        return caractere.encode("cp1252")[0]
    except (UnicodeEncodeError, IndexError):
        return -1


# ------------------------------------------------------------- segments
def _segments(texte: str) -> list[tuple[str, bool]]:
    """Découpe en ``(fragment, en_symbole)``.

    C'EST ICI QUE RIEN NE SE PERD. Chaque caractère est soit représentable en
    WinAnsi, soit une lettre grecque connue, soit une substitution déclarée —
    soit il fait lever.
    """
    morceaux: list[tuple[str, bool]] = []
    courant: list[str] = []
    symbole = False

    def vider() -> None:
        if courant:
            morceaux.append(("".join(courant), symbole))
            courant.clear()

    for brut in texte:
        caractere = _EQUIVALENTS.get(brut, brut)
        for c in caractere:
            en_symbole = c in _GREC
            if not en_symbole and _winansi(c) < 0:
                raise CaractereNonRepresentable(
                    f"le caractere « {c} » (U+{ord(c):04X}) n'a de glyphe ni "
                    "en WinAnsi ni dans la police Symbol. On refuse plutot "
                    "que d'ecrire un document qui aurait perdu un symbole "
                    "sans le dire."
                )
            if en_symbole != symbole:
                vider()
                symbole = en_symbole
            courant.append(c)
    vider()
    return morceaux


def _echapper(fragment: str, symbole: bool) -> bytes:
    """Le littéral de chaîne PDF, octets échappés."""
    if symbole:
        octets = bytes(_GREC[c] for c in fragment)
    else:
        octets = fragment.encode("cp1252")
    sortie = bytearray()
    for o in octets:
        if o in (0x28, 0x29, 0x5C):     # ( ) \
            sortie.append(0x5C)
        sortie.append(o)
    return bytes(sortie)


def _replier(texte: str, police: str, corps: float,
             largeur: float) -> list[str]:
    """Coupe le texte aux espaces pour tenir dans ``largeur``.

    UN MOT PLUS LARGE QUE LA COLONNE N'EST PAS COUPE. Un identifiant, une
    empreinte ou une clause ne se coupent pas au milieu sans devenir faux à
    l'oeil; il deborde, et c'est prefere a un document qui mentirait.
    """
    if not texte:
        return [""]
    lignes: list[str] = []
    courante = ""
    for mot in texte.split(" "):
        essai = f"{courante} {mot}" if courante else mot
        if courante and _largeur(essai, police, corps) > largeur:
            lignes.append(courante)
            courante = mot
        else:
            courante = essai
    lignes.append(courante)
    return lignes


# ------------------------------------------------------------- rendu
class _Page:
    """Le flux de contenu d'une page en construction."""

    __slots__ = ("morceaux", "y")

    def __init__(self) -> None:
        self.morceaux: list[bytes] = []
        self.y: float = PAGE_H - MARGE

    def texte(self, x: float, y: float, contenu: str, police: str,
              corps: float) -> None:
        for fragment, symbole in _segments(contenu):
            if not fragment:
                continue
            nom = SYMBOLE if symbole else police
            self.morceaux.append(
                b"BT /" + nom.encode("ascii") + b" "
                + _nombre(corps) + b" Tf "
                + _nombre(x) + b" " + _nombre(y) + b" Td ("
                + _echapper(fragment, symbole) + b") Tj ET\n")
            x += _largeur(fragment, nom, corps)

    def filet(self, x: float, y: float, largeur: float,
              epaisseur: float = 0.6) -> None:
        self.morceaux.append(
            _nombre(epaisseur) + b" w " + _nombre(x) + b" " + _nombre(y)
            + b" m " + _nombre(x + largeur) + b" " + _nombre(y) + b" l S\n")


def _nombre(valeur: float) -> bytes:
    """Un nombre PDF, sans exposant et sans zéros inutiles.

    LE FORMAT EST FIXE, ET C'EST CE QUI REND LE FICHIER REPRODUCTIBLE: `repr`
    d'un flottant varie avec la plateforme, `%g` bascule en notation
    exponentielle — qu'aucun lecteur PDF n'accepte.
    """
    texte = f"{valeur:.3f}".rstrip("0").rstrip(".")
    return (texte or "0").encode("ascii")


def composer_pdf(titre: str, blocs: list[Bloc]) -> bytes:
    """Compose le document. **Aucune date, aucun identifiant aléatoire.**

    Deux appels avec les mêmes arguments rendent exactement les mêmes octets.
    """
    utile = PAGE_L - 2 * MARGE
    pages: list[_Page] = []

    def nouvelle() -> _Page:
        page = _Page()
        pages.append(page)
        return page

    page = nouvelle()

    def place(hauteur: float) -> _Page:
        """Rend la page courante, ou une neuve si le bloc n'y tient plus."""
        nonlocal page
        if page.y - hauteur < MARGE + 24:
            page = nouvelle()
        return page

    for bloc in blocs:
        if isinstance(bloc, Titre):
            corps = 16.0 if bloc.niveau == 1 else 12.0
            lignes = _replier(bloc.texte, HELVETICA_GRAS, corps, utile)
            p = place(corps * INTERLIGNE * len(lignes) + 10)
            p.y -= 8
            for ligne in lignes:
                p.y -= corps * INTERLIGNE
                p.texte(MARGE, p.y, ligne, HELVETICA_GRAS, corps)
            p.y -= 4

        elif isinstance(bloc, Paragraphe):
            corps = 9.5
            police = HELVETICA_GRAS if bloc.gras else HELVETICA
            decalage = 10.0 if bloc.encadre else 0.0
            lignes = _replier(bloc.texte, police, corps, utile - decalage)
            p = place(corps * INTERLIGNE * len(lignes) + 6)
            haut = p.y
            for ligne in lignes:
                p.y -= corps * INTERLIGNE
                p.texte(MARGE + decalage, p.y, ligne, police, corps)
            if bloc.encadre:
                p.morceaux.append(
                    b"1.4 w " + _nombre(MARGE + 2) + b" " + _nombre(haut)
                    + b" m " + _nombre(MARGE + 2) + b" "
                    + _nombre(p.y - 2) + b" l S\n")
            p.y -= 5

        elif isinstance(bloc, Champs):
            corps = 9.5
            colonne = 165.0
            for libelle, valeur in bloc.paires:
                lignes = _replier(valeur, HELVETICA, corps,
                                  utile - colonne)
                p = place(corps * INTERLIGNE * len(lignes) + 2)
                p.y -= corps * INTERLIGNE
                p.texte(MARGE, p.y, libelle, HELVETICA_GRAS, corps)
                p.texte(MARGE + colonne, p.y, lignes[0], HELVETICA, corps)
                for suite in lignes[1:]:
                    p.y -= corps * INTERLIGNE
                    p.texte(MARGE + colonne, p.y, suite, HELVETICA, corps)
            page.y -= 5

        elif isinstance(bloc, Tableau):
            corps = 8.5
            n = max(1, len(bloc.entetes))
            largeur_col = utile / n
            p = place(corps * INTERLIGNE * 3)
            p.y -= corps * INTERLIGNE
            for i, entete in enumerate(bloc.entetes):
                p.texte(MARGE + i * largeur_col, p.y, entete,
                        HELVETICA_GRAS, corps)
            p.y -= 3
            p.filet(MARGE, p.y, utile)
            for ligne in bloc.lignes:
                cellules = [_replier(str(c), HELVETICA, corps,
                                     largeur_col - 6) for c in ligne]
                hauteur = corps * INTERLIGNE * max(len(c) for c in cellules)
                p = place(hauteur + 2)
                depart = p.y
                for i, morceaux in enumerate(cellules):
                    y = depart
                    for texte in morceaux:
                        y -= corps * INTERLIGNE
                        x = MARGE + i * largeur_col
                        if i in bloc.droite:
                            x += largeur_col - 6 - _largeur(texte, HELVETICA,
                                                            corps)
                        p.texte(x, y, texte, HELVETICA, corps)
                p.y = depart - hauteur
            p.y -= 6

    _paginer(titre, pages)
    return _assembler(titre, pages)


def _paginer(titre: str, pages: list[_Page]) -> None:
    """Le pied de page : le titre à gauche, « page N sur T » à droite.

    UNE NOTE DE CALCUL FINIT RELIEE DANS UN DOSSIER, ET DES PAGES S'Y PERDENT.
    Sans « sur T », personne ne peut constater qu'il manque la derniere ; sans
    le titre, une page detachee n'appartient plus a rien. C'est la difference
    entre un document imprimable et un document opposable.

    IL S'ECRIT APRES LA COMPOSITION, ET IL LE FAUT: le total n'est connu
    qu'une fois toutes les pages remplies. C'est aussi pourquoi il ne consomme
    pas ``page.y`` — il vit SOUS la zone de contenu, dans la marge basse que
    la composition ne descend jamais toucher.
    """
    total = len(pages)
    corps = 7.5
    ligne_y = MARGE - 18.0
    for numero, page in enumerate(pages, start=1):
        page.filet(MARGE, ligne_y + 10, PAGE_L - 2 * MARGE, 0.4)
        page.texte(MARGE, ligne_y, titre, HELVETICA, corps)
        compteur = f"page {numero} sur {total}"
        page.texte(PAGE_L - MARGE - _largeur(compteur, HELVETICA, corps),
                   ligne_y, compteur, HELVETICA, corps)


def _assembler(titre: str, pages: list[_Page]) -> bytes:
    """Les objets, la table de références croisées, la fin de fichier."""
    if not pages:
        pages = [_Page()]

    objets: list[bytes] = []

    def ajouter(corps: bytes) -> int:
        objets.append(corps)
        return len(objets)     # les numeros d'objet commencent a 1

    # 1 catalogue, 2 pages, puis les polices, puis page+flux par page.
    n_catalogue = ajouter(b"")     # rempli plus bas
    n_pages = ajouter(b"")
    polices = {
        HELVETICA: ajouter(b"<< /Type /Font /Subtype /Type1 "
                           b"/BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"),
        HELVETICA_GRAS: ajouter(b"<< /Type /Font /Subtype /Type1 "
                                b"/BaseFont /Helvetica-Bold "
                                b"/Encoding /WinAnsiEncoding >>"),
        COURIER: ajouter(b"<< /Type /Font /Subtype /Type1 "
                         b"/BaseFont /Courier /Encoding /WinAnsiEncoding >>"),
        # LA POLICE `Symbol` N'A PAS D'ENCODAGE DECLARE, et c'est voulu: elle
        # porte son propre encodage integre, et lui imposer WinAnsi ferait
        # afficher des lettres latines a la place des grecques.
        SYMBOLE: ajouter(b"<< /Type /Font /Subtype /Type1 /BaseFont /Symbol >>"),
    }

    ressources = (b"<< /Font << " + b" ".join(
        b"/" + nom.encode("ascii") + b" " + str(num).encode("ascii") + b" 0 R"
        for nom, num in polices.items()) + b" >> >>")

    numeros_pages: list[int] = []
    for page in pages:
        flux = b"".join(page.morceaux)
        # LA COMPRESSION EST DETERMINISTE: `zlib.compress` a niveau fixe rend
        # les memes octets pour les memes entrees, sur toute plateforme.
        comprime = zlib.compress(flux, 9)
        n_flux = ajouter(b"<< /Length " + str(len(comprime)).encode("ascii")
                         + b" /Filter /FlateDecode >>\nstream\n" + comprime
                         + b"\nendstream")
        n_page = ajouter(b"")
        numeros_pages.append(n_page)
        objets[n_page - 1] = (
            b"<< /Type /Page /Parent " + str(n_pages).encode("ascii")
            + b" 0 R /MediaBox [0 0 " + _nombre(PAGE_L) + b" "
            + _nombre(PAGE_H) + b"] /Resources " + ressources
            + b" /Contents " + str(n_flux).encode("ascii") + b" 0 R >>")

    objets[n_pages - 1] = (
        b"<< /Type /Pages /Count " + str(len(numeros_pages)).encode("ascii")
        + b" /Kids [" + b" ".join(str(n).encode("ascii") + b" 0 R"
                                  for n in numeros_pages) + b"] >>")
    objets[n_catalogue - 1] = (
        b"<< /Type /Catalog /Pages " + str(n_pages).encode("ascii") + b" 0 R >>")

    # LE TITRE VOYAGE, MAIS AUCUNE DATE NI AUCUN PRODUCTEUR VERSIONNE.
    # `/CreationDate` ferait changer l'empreinte du livrable a chaque
    # composition, alors qu'aucun chiffre du document n'aurait bouge.
    fragments = _segments(titre)
    titre_pdf = b"".join(_echapper(f, s) for f, s in fragments if not s)
    n_info = ajouter(b"<< /Title (" + titre_pdf + b") >>")

    sortie = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    decalages: list[int] = []
    for numero, corps in enumerate(objets, start=1):
        decalages.append(len(sortie))
        sortie += str(numero).encode("ascii") + b" 0 obj\n" + corps + b"\nendobj\n"

    debut_xref = len(sortie)
    sortie += b"xref\n0 " + str(len(objets) + 1).encode("ascii") + b"\n"
    sortie += b"0000000000 65535 f \n"
    for decalage in decalages:
        sortie += f"{decalage:010d} 00000 n \n".encode("ascii")
    sortie += (b"trailer\n<< /Size " + str(len(objets) + 1).encode("ascii")
               + b" /Root " + str(n_catalogue).encode("ascii") + b" 0 R"
               + b" /Info " + str(n_info).encode("ascii") + b" 0 R >>\n"
               + b"startxref\n" + str(debut_xref).encode("ascii")
               + b"\n%%EOF\n")
    return bytes(sortie)
