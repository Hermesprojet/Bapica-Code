"""Les règles de lecture : des écritures courantes en français, néerlandais et
anglais, vers des propositions.

CE QUE CES RÈGLES SONT, ET CE QU'ELLES NE SONT PAS
---------------------------------------------------
Des motifs déterministes sur le texte lu. Mêmes lignes, mêmes propositions.
Aucun modèle de langage (interdiction 1), aucune valeur qui ne soit écrite
dans le document (interdiction 2) : une règle ne complète jamais un nombre,
ne déduit jamais une grandeur d'une autre, ne convertit jamais une unité.

UNE PROPOSITION NE DIT QUE CE QUE LA RÈGLE A VU. Le texte brut de la ligne
voyage avec elle, la boîte couvre les mots reconnus, et ``fondement`` nomme la
règle et l'origine de l'unité. Quand une règle s'appuie sur une convention de
notation — « 30x60 » se lit largeur × hauteur, « HA20 » est un diamètre en
millimètres, « +3,20 » une altitude en mètres —, elle le DIT, et la confiance
baisse d'autant.

LE RAPPEL EST PARTIEL, ET C'EST ÉCRIT DANS ``docs/LECTURE_DES_PLANS.md``. Une
grandeur qu'aucune règle ne voit n'est pas proposée ; l'ingénieur la saisit,
comme avant.

UN MÊME MORCEAU DE TEXTE NE NOURRIT QU'UNE PROPOSITION. Les règles passent
dans un ordre fixe et « consomment » ce qu'elles reconnaissent : « C30/37 »
n'est pas aussi lu comme une section 30/37, « portée 6,00 m » n'est pas aussi
lu comme une épaisseur de dalle.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final

from ..modele import Candidat
from ..nombres import NOMBRE, NOMBRE_AVEC_MILLIERS, lire_nombre
from .lignes import Ligne
from .unites import Declaration, unite_declaree

__all__ = ["Contexte", "extraire_des_lignes"]

#: Une lecture OCR ne vaut jamais plus que cela, quelle que soit la règle.
PLAFOND_OCR: Final[float] = 0.60
PLANCHER: Final[float] = 0.05
PLAFOND: Final[float] = 0.95

#: Ce que coûte une unité qui n'est pas écrite à côté du nombre.
PENALITE_UNITE: Final[dict[str, float]] = {
    "explicite": 0.0, "declaration": 0.05, "convention": 0.10, "absente": 0.25,
}

#: EN 206, tableaux 12 et 13 : les classes de résistance. La liste ne fixe
#: aucune valeur — elle sert à ne proposer que des DÉSIGNATIONS qui existent,
#: plutôt qu'une fraction quelconque précédée d'un C.
CLASSES_BETON: Final[frozenset[str]] = frozenset({
    "C8/10", "C12/15", "C16/20", "C20/25", "C25/30", "C30/37", "C35/45",
    "C40/50", "C45/55", "C50/60", "C55/67", "C60/75", "C70/85", "C80/95",
    "C90/105", "C100/115",
    "LC8/9", "LC12/13", "LC16/18", "LC20/22", "LC25/28", "LC30/33", "LC35/38",
    "LC40/44", "LC45/50", "LC50/55", "LC55/60", "LC60/66", "LC70/77", "LC80/88",
})

#: Les diamètres de barres du commerce : un « 4 HA 23 » n'est pas une barre.
DIAMETRES: Final[frozenset[int]] = frozenset({5, 6, 8, 10, 12, 14, 16, 20, 25, 28, 32, 40})

_U_LONG = r"(?P<u>mm|cm|m)(?![\w²³/^])"
#: L'unite FACULTATIVE: le groupe entier est optionnel, pas son assertion.
_U_OPT = r"(?:" + _U_LONG + r")?"
_REPERE = r"\b[A-Z]{1,3}\s?-?\s?\d{1,3}[a-z]?\b"
_KW_POUTRE = r"(?i:poutres?|balken|balk|beams?|linteaux|linteau|lintels?|sommiers?|latei)"
_KW_POTEAU = r"(?i:poteaux|poteau|colonnes?|kolommen|kolom|columns?|piliers?)"


@dataclass
class Contexte:
    """Ce qu'une règle sait du document au-delà de sa ligne."""

    declarations: list[Declaration] = field(default_factory=list)


class _Fabrique:
    """Fabrique les propositions d'UNE ligne, et tient ce qui est consommé."""

    def __init__(self, ligne: Ligne, contexte: Contexte) -> None:
        self.ligne = ligne
        self.contexte = contexte
        self.consomme: list[tuple[int, int]] = []
        self.candidats: list[Candidat] = []

    def libre(self, debut: int, fin: int) -> bool:
        return all(fin <= d or debut >= f for d, f in self.consomme)

    def consommer(self, debut: int, fin: int) -> None:
        self.consomme.append((debut, fin))

    def proposer(self, categorie: str, valeur: Any, debut: int, fin: int, *,
                 base: float, regle: str, unite: str | None = None,
                 nature: str = "longueur", convention: str | None = None,
                 repere: str | None = None, extra: dict[str, Any] | None = None,
                 ) -> None:
        ligne = self.ligne
        fondement: dict[str, Any] = {"rule": regle}
        if nature in ("longueur", "charge", "niveau"):
            if unite:
                fondement["unit_basis"] = "explicite"
            elif convention:
                unite = _unite_de_convention(convention)
                fondement["unit_basis"] = "convention"
                fondement["convention"] = convention
            else:
                declaration = unite_declaree(ligne.page, self.contexte.declarations)
                if declaration is not None:
                    unite = declaration.unite
                    fondement["unit_basis"] = "declaration"
                    fondement["unit_declaration"] = declaration.citation()
                else:
                    fondement["unit_basis"] = "absente"
        if extra:
            fondement.update(extra)

        confiance = base
        if ligne.methode == "ocr":
            lue = ligne.confiance_ocr(debut, fin)
            confiance = min(confiance, PLAFOND_OCR, lue if lue is not None else PLAFOND_OCR)
        confiance -= PENALITE_UNITE.get(fondement.get("unit_basis", "explicite"), 0.0)
        confiance = round(min(max(confiance, PLANCHER), PLAFOND), 3)

        self.candidats.append(Candidat(
            categorie=categorie, valeur=valeur, unite=unite,
            texte_brut=ligne.texte_brut, page=ligne.page, confiance=confiance,
            methode=ligne.methode, boite=ligne.boite_de(debut, fin),
            position=ligne.position_de(), repere=repere, fondement=fondement))


def _unite_de_convention(convention: str) -> str:
    return {"diametre_mm": "mm", "niveau_m": "m"}[convention]


def _repere(texte: str | None) -> str | None:
    if not texte:
        return None
    return re.sub(r"[\s-]", "", texte).upper() or None


def _n(texte: str) -> int | float:
    return lire_nombre(texte)


# --------------------------------------------------------------- les règles
_BETON = re.compile(r"(?<![\w/])(?P<c>L?C)\s?(?P<a>\d{1,3})\s?/\s?(?P<b>\d{1,3})(?![\w/])")


def _classe_beton(f: _Fabrique) -> None:
    for m in _BETON.finditer(f.ligne.texte):
        designation = f"{m.group('c')}{int(m.group('a'))}/{int(m.group('b'))}"
        if designation not in CLASSES_BETON or not f.libre(m.start(), m.end()):
            continue
        f.consommer(m.start(), m.end())
        f.proposer("concrete_class", designation, m.start(), m.end(), base=0.85,
                   regle="classe_beton_en206", nature="texte")


_EXPOSITION = re.compile(r"(?<![\w])(?P<x>X0|XC[1-4]|XD[1-3]|XS[1-3]|XF[1-4]|XA[1-3])(?![\w])")


def _classe_exposition(f: _Fabrique) -> None:
    for m in _EXPOSITION.finditer(f.ligne.texte):
        if not f.libre(m.start(), m.end()):
            continue
        f.consommer(m.start(), m.end())
        f.proposer("exposure_class", m.group("x"), m.start(), m.end(), base=0.85,
                   regle="classe_exposition_en206", nature="texte")


_ACIER = re.compile(
    r"(?<![\w])(?P<g>B\s?500\s?(?:SD|[ABCS])|B\s?450\s?C|BE\s?[45]00\s?[SD]?|"
    r"Fe\s?E\s?[45]00|S\s?(?:235|275|355|420|460)(?:\s?(?:JR|J0|J2|K2|NL|ML|N|M|W|H))?)"
    r"(?![\w])")


def _nuance_acier(f: _Fabrique) -> None:
    for m in _ACIER.finditer(f.ligne.texte):
        if not f.libre(m.start(), m.end()):
            continue
        f.consommer(m.start(), m.end())
        f.proposer("steel_grade", re.sub(r"\s", "", m.group("g")), m.start(), m.end(),
                   base=0.8, regle="nuance_acier", nature="texte")


_UNITES_CHARGE: Final[dict[str, str]] = {
    "kN/m²": "kN/m^2", "kN/m2": "kN/m^2", "kN/m^2": "kN/m^2",
    "kN/m³": "kN/m^3", "kN/m3": "kN/m^3", "kN/m^3": "kN/m^3",
    "kN/ml": "kN/m", "kN/m": "kN/m", "kN": "kN", "kPa": "kPa",
    "daN/m²": "daN/m^2", "daN/m2": "daN/m^2", "kg/m²": "kg/m^2", "kg/m2": "kg/m^2",
}
#: Les noms de charge, en toutes lettres. Le symbole seul (G, Q) est admis
#: aussi, mais il dit moins: voir `_charge`.
_MOTS_CHARGE = (
    r"(?i:charges?\s+(?:d['’]\s?exploitation|permanentes?|utiles?|de\s+neige|"
    r"de\s+vent|de\s+cloisons?|d['’]\s?entretien|climatiques?)|surcharges?"
    r"(?:\s+d['’]\s?exploitation)?|nuttige\s+(?:last|belasting)|permanente\s+"
    r"(?:last|belasting)|sneeuwbelasting|windbelasting|imposed\s+loads?|live\s+loads?|"
    r"dead\s+loads?|superimposed\s+(?:dead\s+)?loads?|snow\s+loads?|wind\s+loads?)")
_CHARGE = re.compile(
    r"(?P<kw>" + _MOTS_CHARGE + r"|\b[GQgq]k?\b)"
    r"\s*[:=]?\s*(?P<n>" + NOMBRE + r")\s*"
    r"(?P<u>kN/m²|kN/m2|kN/m\^2|kN/m³|kN/m3|kN/m\^3|kN/ml|kN/m|kN|kPa|daN/m²|daN/m2|"
    r"kg/m²|kg/m2)(?![\w])")


def _nature_de_charge(mot: str) -> str:
    bas = mot.lower()
    if any(k in bas for k in ("exploitation", "utile", "nuttige", "imposed", "live")):
        return "exploitation"
    if any(k in bas for k in ("permanent", "dead", "superimposed")):
        return "permanente"
    if any(k in bas for k in ("neige", "sneeuw", "snow")):
        return "neige"
    if any(k in bas for k in ("vent", "wind")):
        return "vent"
    if "cloison" in bas:
        return "cloisons"
    if "entretien" in bas:
        return "entretien"
    if bas.startswith("q"):
        return "variable (Q)"
    if bas.startswith("g"):
        return "permanente (G)"
    return "non precisee"


_CHARGE_NOMMEE = re.compile(r"(?P<kw>" + _MOTS_CHARGE + r")")


def _charge(f: _Fabrique) -> None:
    for m in _CHARGE.finditer(f.ligne.texte):
        if not f.libre(m.start(), m.end()):
            continue
        f.consommer(m.start(), m.end())
        mot = m.group("kw")
        base = 0.7
        if len(mot.strip()) <= 2:
            # « Charge d'exploitation Q = 2,5 kN/m² »: le symbole est colle au
            # nombre, le nom de la charge est plus tot sur la ligne. C'est lui
            # qui dit la nature; sans lui, le symbole seul vaut moins.
            nommee = _CHARGE_NOMMEE.search(f.ligne.texte[: m.start()])
            if nommee is not None:
                mot = nommee.group("kw")
            else:
                base = 0.55
        f.proposer("load_value", _n(m.group("n")), m.start(), m.end(),
                   base=base, regle="charge",
                   unite=_UNITES_CHARGE[m.group("u")], nature="charge",
                   extra={"load_nature": _nature_de_charge(mot)})


_NIVEAU = re.compile(
    r"(?P<kw>(?i:niveaux?|niv\.|peil|level|lvl|altitude|TOP|NGF|AN)\b)?\s*[:=]?\s*"
    r"(?P<s>[+\-−±])\s?(?P<n>\d{1,3}[.,]\d{2,3})(?![\d.,])\s*(?P<u>m(?![\w²³/^]))?")
_NOM_NIVEAU = re.compile(
    r"(?i:\b(?:R\s?[+\-]\s?\d{1,2}|RDC|rez(?:-de-chauss[ée]e)?|sous-sol|SS\d?|"
    r"N\s?[+\-]\s?\d{1,2}|(?:niveau|[ée]tage|verdieping|level|floor)\s+[+\-]?\d{1,2}(?![.,]\d)|"
    r"gelijkvloers|kelder|toiture|dak|roof)\b)")


def _niveau(f: _Fabrique) -> None:
    texte = f.ligne.texte
    for m in _NIVEAU.finditer(texte):
        debut = m.start("s")
        if m.group("kw"):
            debut = m.start("kw")
        if not f.libre(debut, m.end()):
            continue
        signe = m.group("s")
        valeur = _n(m.group("n"))
        if signe in "-−":
            valeur = -valeur
        elif signe == "±" and valeur != 0:
            continue
        nom = None
        for n in _NOM_NIVEAU.finditer(texte):
            if n.end() <= m.start("s") or n.start() >= m.end():
                nom = n.group(0)
                break
        f.consommer(debut, m.end())
        f.proposer("floor_level", valeur, debut, m.end(),
                   base=0.7 if m.group("kw") else 0.5, regle="niveau_signe",
                   unite="m" if m.group("u") else None, nature="niveau",
                   convention=None if m.group("u") else "niveau_m",
                   repere=nom.strip() if nom else None)


_HAUTEUR_ETAGE = re.compile(
    r"(?P<kw>(?i:hauteurs?\s+d['’]\s?[ée]tages?|hauteurs?\s+[ée]tages?|hauteur\s+entre\s+"
    r"planchers|verdiepingshoogtes?|(?:storey|story)\s+heights?|floor[\s-]to[\s-]floor"
    r"(?:\s+heights?)?))\s*[:=]?\s*(?P<n>" + NOMBRE + r")\s*" + _U_OPT)


def _hauteur_etage(f: _Fabrique) -> None:
    for m in _HAUTEUR_ETAGE.finditer(f.ligne.texte):
        if not f.libre(m.start(), m.end()):
            continue
        f.consommer(m.start(), m.end())
        f.proposer("story_height", _n(m.group("n")), m.start(), m.end(), base=0.75,
                   regle="hauteur_etage", unite=m.group("u"))


_CADRES = re.compile(
    r"(?P<kw>(?i:cadres?|cad\.|[ée]triers?|[ée]pingles?|beugels?|stirrups?|links?|"
    r"ligatures?))\s*(?:(?P<nb>\d)\s*[x×]\s*)?(?:HA|T|Ø|ø|⌀|φ|Φ)\s*(?P<d>\d{1,2})(?![\d.,])"
    r"(?:\s*(?:(?i:e\s*=|esp\.?\s*=?|s\s*=|tous\s+les|om\s+de)|@|/|-)\s*"
    r"(?P<s>" + NOMBRE + r")\s*" + _U_OPT + r")?")


def _cadres(f: _Fabrique) -> None:
    for m in _CADRES.finditer(f.ligne.texte):
        diametre = int(m.group("d"))
        if diametre not in DIAMETRES or not f.libre(m.start(), m.end()):
            continue
        f.consommer(m.start(), m.end())
        repere = _repere(_premier(_REPERE_POUTRE, f.ligne.texte))
        f.proposer("link_diameter", diametre, m.start(), m.end(), base=0.65,
                   regle="cadres", convention="diametre_mm", repere=repere)
        if m.group("s"):
            f.proposer("link_spacing", _n(m.group("s")), m.start(), m.end(),
                       base=0.6, regle="cadres_espacement", unite=m.group("u"),
                       repere=repere)


_BARRES = re.compile(
    r"(?<![\w/.,])(?P<nb>\d{1,2})\s*(?P<sym>HA|T|Ø|ø|⌀|φ|Φ)\s*(?P<d>\d{1,2})(?![\d.,])")
_REPERE_POUTRE = re.compile(r"\b(?:P|B|BM|BA|PT|POU)\s?-?\s?\d{1,3}[a-z]?\b")


def _premier(motif: re.Pattern[str], texte: str) -> str | None:
    m = motif.search(texte)
    return m.group(0) if m else None


def _barres(f: _Fabrique) -> None:
    for m in _BARRES.finditer(f.ligne.texte):
        diametre = int(m.group("d"))
        if diametre not in DIAMETRES or not f.libre(m.start(), m.end()):
            continue
        f.consommer(m.start(), m.end())
        repere = _repere(_premier(_REPERE_POUTRE, f.ligne.texte))
        f.proposer("bar_count", int(m.group("nb")), m.start(), m.end(), base=0.65,
                   regle="barres", nature="entier", repere=repere)
        f.proposer("bar_diameter", diametre, m.start(), m.end(), base=0.65,
                   regle="barres", convention="diametre_mm", repere=repere)


_POTEAU_ROND = re.compile(
    r"(?P<kw>" + _KW_POTEAU + r")\s*(?P<rep>" + _REPERE + r")?\s*[:(]?\s*"
    r"(?:[ØøΦφ⌀]|(?i:diam(?:[èe]tre)?\.?)|D\s*=)\s*(?P<n>" + NOMBRE + r")\s*"
    + _U_OPT)


def _poteau_rond(f: _Fabrique) -> None:
    for m in _POTEAU_ROND.finditer(f.ligne.texte):
        if not f.libre(m.start(), m.end()):
            continue
        f.consommer(m.start(), m.end())
        f.proposer("column_diameter", _n(m.group("n")), m.start(), m.end(), base=0.6,
                   regle="poteau_circulaire", unite=m.group("u"),
                   repere=_repere(m.group("rep")))


_SECTION = re.compile(
    r"(?P<kw>" + _KW_POUTRE + r"|" + _KW_POTEAU + r")?\s*(?P<rep>" + _REPERE + r")?"
    r"\s*[:(]?\s*(?P<a>" + NOMBRE + r")\s*(?P<sep>[x×X*]|/)\s*(?P<b>" + NOMBRE + r")"
    r"\s*" + _U_OPT)
_PREFIXES_POUTRE: Final[frozenset[str]] = frozenset({"P", "B", "BM", "BA", "PT", "POU", "L"})
_PREFIXES_POTEAU: Final[frozenset[str]] = frozenset({"C", "K", "COL", "PO", "POT"})


def _sections(f: _Fabrique) -> None:
    for m in _SECTION.finditer(f.ligne.texte):
        kw, rep = m.group("kw"), m.group("rep")
        if not kw and not rep:
            continue
        debut = m.start("kw") if kw else m.start("rep")
        if not f.libre(debut, m.end()):
            continue
        if kw:
            poteau = re.fullmatch(_KW_POTEAU, kw.strip()) is not None
            classement = "mot_cle"
            base = 0.65
        else:
            prefixe = re.match(r"[A-Z]+", rep or "")
            lettres = prefixe.group(0) if prefixe else ""
            if lettres in _PREFIXES_POTEAU:
                poteau = True
            elif lettres in _PREFIXES_POUTRE:
                poteau = False
            else:
                continue
            classement = f"prefixe_de_repere:{lettres}"
            base = 0.45
        f.consommer(debut, m.end())
        largeur, profondeur = (("column_width", "column_depth") if poteau
                               else ("beam_width", "beam_depth"))
        extra = {"convention_section": ("largeur x profondeur" if poteau
                                        else "largeur x hauteur (b x h)"),
                 "classement": classement}
        for categorie, groupe in ((largeur, "a"), (profondeur, "b")):
            f.proposer(categorie, _n(m.group(groupe)), debut, m.end(), base=base,
                       regle="section_rectangulaire", unite=m.group("u"),
                       repere=_repere(rep), extra=extra)


_PORTEE = re.compile(
    r"(?P<kw>(?i:port[ée]es?|overspanning(?:slengte)?|spans?|l\s?eff|l_eff))\b\s*"
    r"(?:(?i:de\s+la\s+poutre|van\s+de\s+balk|of\s+beam)\s*)?(?P<rep>" + _REPERE + r")?"
    r"\s*[:=]?\s*(?P<n>" + NOMBRE + r")\s*" + _U_OPT)
_PORTEE_L = re.compile(r"(?<![\w])L\s*=\s*(?P<n>" + NOMBRE + r")\s*" + _U_LONG)


def _portee(f: _Fabrique) -> None:
    texte = f.ligne.texte
    for m in _PORTEE.finditer(texte):
        if not f.libre(m.start(), m.end()):
            continue
        f.consommer(m.start(), m.end())
        repere = m.group("rep") or _premier(_REPERE_POUTRE, texte)
        f.proposer("beam_span", _n(m.group("n")), m.start(), m.end(), base=0.7,
                   regle="portee", unite=m.group("u"), repere=_repere(repere))
    # « L = 6,00 m » NE DIT UNE PORTEE QUE SUR UNE LIGNE DE POUTRE: ailleurs,
    # c'est une longueur quelconque.
    if re.search(_KW_POUTRE, texte) or _REPERE_POUTRE.search(texte):
        for m in _PORTEE_L.finditer(texte):
            if not f.libre(m.start(), m.end()):
                continue
            f.consommer(m.start(), m.end())
            f.proposer("beam_span", _n(m.group("n")), m.start(), m.end(), base=0.45,
                       regle="longueur_L_sur_ligne_de_poutre", unite=m.group("u"),
                       repere=_repere(_premier(_REPERE_POUTRE, texte)))


_EPAISSEUR = (r"(?P<ep>(?i:[ée]p(?:aisseur)?\.?|e\s*=|ep\s*=|dikte|d\s*=|h\s*=|"
              r"thickness|thk\.?|th\.))")
_DALLE = re.compile(
    r"(?P<kw>(?i:dalles?|planchers?|hourdis|pr[ée]dalles?|vloerplaat|vloer|druklaag|"
    r"slabs?|deck))\b(?P<entre>[^\d\n+\-−±]{0,30}?)" + _EPAISSEUR + r"?\s*[:=]?\s*"
    r"(?<![+\-−±])(?P<n>" + NOMBRE + r")\s*" + _U_OPT)
_VOILE = re.compile(
    r"(?P<kw>(?i:voiles?|murs?|wanden|wand|muur|walls?))\b(?P<entre>[^\d\n+\-−±]{0,30}?)"
    + _EPAISSEUR + r"\s*[:=]?\s*(?<![+\-−±])(?P<n>" + NOMBRE + r")\s*" + _U_OPT)


def _epaisseurs(f: _Fabrique) -> None:
    for motif, categorie, exige_mot in ((_DALLE, "slab_thickness", False),
                                        (_VOILE, "wall_thickness", True)):
        for m in motif.finditer(f.ligne.texte):
            if not m.group("ep") and (exige_mot or not m.group("u")):
                continue
            if not f.libre(m.start(), m.end()):
                continue
            f.consommer(m.start(), m.end())
            f.proposer(categorie, _n(m.group("n")), m.start(), m.end(),
                       base=0.7 if m.group("ep") else 0.45,
                       regle=("epaisseur_nommee" if m.group("ep")
                              else "epaisseur_supposee_unite_seule"),
                       unite=m.group("u"))


_ENROBAGE = re.compile(
    r"(?P<kw>(?i:enrobages?(?:\s+nominal)?|c\s?nom|c_nom|betondekking|dekking|"
    r"(?:concrete\s+)?cover))\b\s*(?:(?i:de|van|of|min(?:imum)?\.?)\s*)?[:=]?\s*"
    r"(?P<n>" + NOMBRE + r")\s*(?P<u>mm|cm)?(?![\w²/])")


def _enrobage(f: _Fabrique) -> None:
    for m in _ENROBAGE.finditer(f.ligne.texte):
        if not f.libre(m.start(), m.end()):
            continue
        f.consommer(m.start(), m.end())
        f.proposer("concrete_cover", _n(m.group("n")), m.start(), m.end(), base=0.75,
                   regle="enrobage", unite=m.group("u"))


_AXE = re.compile(
    r"(?P<kw>(?i:axes?|files?|grid(?:lines?)?|stramien(?:lijnen|lijn)?|assen|as))\s+"
    r"(?P<a>[A-Z]{1,2}|\d{1,2})(?![\w,.])"
    r"(?:\s*(?:-|–|/|(?i:tot|to))\s*(?P<b>[A-Z]{1,2}|\d{1,2})(?![\w,.]))?"
    r"(?:\s*[:=]?\s*(?P<n>" + NOMBRE + r")\s*" + _U_OPT + r")?")


def _axes(f: _Fabrique) -> None:
    for m in _AXE.finditer(f.ligne.texte):
        a, b = m.group("a"), m.group("b")
        if b is not None and a.isalpha() != b.isalpha():
            b = None
        if not f.libre(m.start(), m.end()):
            continue
        f.consommer(m.start(), m.end())
        if b is not None and m.group("n"):
            f.proposer("grid_spacing", _n(m.group("n")), m.start(), m.end(), base=0.6,
                       regle="entraxe_nomme", unite=m.group("u"), repere=f"{a}-{b}")
            continue
        for etiquette in (a, b):
            if etiquette is not None:
                f.proposer("grid_line", etiquette, m.start(), m.end(), base=0.55,
                           regle="axe_nomme", nature="texte")


_BATIMENT = re.compile(
    r"(?P<kw>(?i:longueur\s+(?:totale|du\s+b[âa]timent|hors\s+tout)|largeur\s+(?:totale|"
    r"du\s+b[âa]timent|hors\s+tout)|hauteur\s+(?:totale|du\s+b[âa]timent|hors\s+tout|au\s+"
    r"fa[iî]tage)|emprise(?:\s+au\s+sol)?|totale\s+(?:lengte|breedte|hoogte)|(?:overall|"
    r"building)\s+(?:length|width|height)|gebouw(?:lengte|breedte|hoogte)))\s*[:=]?\s*"
    r"(?P<a>" + NOMBRE_AVEC_MILLIERS + r"|" + NOMBRE + r")\s*(?:(?P<sep>[x×X])\s*"
    r"(?P<b>" + NOMBRE_AVEC_MILLIERS + r"|" + NOMBRE + r"))?\s*" + _U_OPT)


def _batiment(f: _Fabrique) -> None:
    for m in _BATIMENT.finditer(f.ligne.texte):
        if not f.libre(m.start(), m.end()):
            continue
        f.consommer(m.start(), m.end())
        mot = " ".join(m.group("kw").lower().split())
        for rang, groupe in enumerate(("a", "b"), start=1):
            if m.group(groupe) is None:
                continue
            extra = {"dimension": mot}
            if m.group("b") is not None:
                extra["axis"] = rang
            f.proposer("building_dimension", _n(m.group(groupe)), m.start(), m.end(),
                       base=0.65, regle="dimension_du_batiment", unite=m.group("u"),
                       extra=extra)


_MATERIAU = re.compile(
    r"(?i:\b(?:b[ée]ton|concrete|acier|aciers|staal|steel|armatures?|wapening|"
    r"reinforcement|ma[çc]onnerie|metselwerk|bois|hout|timber)\b)")
_PRECISION_MATERIAU = re.compile(r"(?i:\bdmax\b|\bclasse\b|\bklasse\b|\bclass\b|\bCEM\b)")


def _specification_materiau(f: _Fabrique) -> None:
    texte = f.ligne.texte
    if not _MATERIAU.search(texte):
        return
    if not (_BETON.search(texte) or _ACIER.search(texte) or _EXPOSITION.search(texte)
            or _PRECISION_MATERIAU.search(texte)):
        return
    f.proposer("material_specification", f.ligne.texte_brut, 0, len(texte), base=0.6,
               regle="ligne_de_specification", nature="texte")


#: L'ORDRE EST UNE REGLE: les designations et les grandeurs a mot-cle d'abord,
#: les formes les plus ambigues (sections, epaisseurs, axes) ensuite.
_REGLES: Final[tuple[Callable[[_Fabrique], None], ...]] = (
    _classe_beton, _classe_exposition, _nuance_acier, _charge, _niveau,
    _hauteur_etage, _cadres, _barres, _poteau_rond, _sections, _portee,
    _epaisseurs, _enrobage, _axes, _batiment, _specification_materiau,
)

_NOTE = re.compile(
    r"^\s*(?P<kw>(?i:notes?|n\.?\s?b\.?|remarques?|nota|opmerkingen|opmerking|important|"
    r"attention|let\s+op))\s*(?:\d+\s*)?[:\-–.]\s*(?P<corps>\S.*)$")
_ENTETE_NOTES = re.compile(
    r"^\s*(?i:notes?(?:\s+g[ée]n[ée]rales?)?|remarques?(?:\s+g[ée]n[ée]rales?)?|"
    r"opmerkingen|algemene\s+opmerkingen|general\s+notes)\s*:?\s*$")
_PUCE = re.compile(r"^\s*(?:[-–•·*]|\d{1,2}[.)])\s+\S")

#: Un bloc de notes s'arrete apres ce nombre de lignes, ou a la premiere ligne
#: qui n'est pas une puce.
LIGNES_MAX_BLOC: Final[int] = 20


def _notes(lignes: list[Ligne], contexte: Contexte) -> list[Candidat]:
    candidats: list[Candidat] = []
    dans_bloc = 0
    page_bloc = None
    for ligne in lignes:
        if page_bloc is not None and ligne.page != page_bloc:
            dans_bloc = 0
        f = _Fabrique(ligne, contexte)
        if _ENTETE_NOTES.match(ligne.texte):
            dans_bloc, page_bloc = LIGNES_MAX_BLOC, ligne.page
            continue
        if _NOTE.match(ligne.texte):
            f.proposer("structural_note", ligne.texte_brut, 0, len(ligne.texte),
                       base=0.6, regle="note_introduite", nature="texte")
        elif dans_bloc and _PUCE.match(ligne.texte):
            f.proposer("structural_note", ligne.texte_brut, 0, len(ligne.texte),
                       base=0.55, regle="note_dans_un_bloc_de_notes", nature="texte")
            dans_bloc -= 1
            candidats.extend(f.candidats)
            continue
        else:
            dans_bloc = 0
        candidats.extend(f.candidats)
    return candidats


def extraire_des_lignes(lignes: list[Ligne], contexte: Contexte) -> list[Candidat]:
    """Toutes les propositions des lignes, dans l'ordre de lecture."""
    candidats: list[Candidat] = []
    for ligne in lignes:
        f = _Fabrique(ligne, contexte)
        for regle in _REGLES:
            regle(f)
        candidats.extend(f.candidats)
    candidats.extend(_notes(lignes, contexte))
    return candidats
