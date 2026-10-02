"""L'information DXF standard (N1) lue par la phase G1 — et rien de plus.

Voir ``docs/GEOMETRIE_D_ABORD_G1.md``. Chaque champ nouveau des primitives
est lu tel que le DXF le porte (F1 à F7) ; AUCUNE sortie ne change : les
champs sont hors égalité, une multiligne reste comptée « entité non lue », et
neutraliser la lecture N1 — ou la rendre illisible — donne exactement les
mêmes sorties.
"""

from __future__ import annotations

import dataclasses
import json
import math

import pytest

from eurostruct_extraction import extract_engineering_data, parse_document
from eurostruct_extraction.geometrie import primitives as module_primitives
from eurostruct_extraction.geometrie.primitives import (
    DefinitionDeBloc,
    PrimitivesDxf,
    Segment,
    Source,
    classe_de_motif,
)
from fabrique_geometrie import MOTIFS_N1, dxf_fondations_pieux, dxf_information_n1


@pytest.fixture(scope="module")
def plan() -> PrimitivesDxf:
    return parse_document(dxf_information_n1()).primitives_dxf


def _segment(plan: PrimitivesDxf, y: float, *, bloc: str | None = None) -> Segment:
    trouves = [s for s in plan.segments if abs(s.a[1] - y) < 1e-6
               and (bloc is None or bloc in s.source.blocs)]
    assert len(trouves) == 1, (y, bloc, trouves)
    return trouves[0]


# ============================================================ F1 — motifs
@pytest.mark.parametrize(("elements", "classe"), [
    ((), "continu"),                                  # Continuous, ByLayer
    ((1.0,), "continu"),                              # aucun blanc
    ((-1.0,), "continu"),                             # aucun trait : dégénéré
    ((3.175, -0.635, 0.635, -0.635), "mixte"),        # CENTER : trait court
    ((2.54, -0.508, 0.0, -0.508), "mixte"),           # DASHDOT : point
    ((3.175, -0.635, 0.635, -0.635, 0.635, -0.635), "mixte"),  # PHANTOM
    ((24.0, -3.0, 0.5, -3.0), "mixte"),               # ACAD_ISO04W100 : 0,5 ≤ 0,2 × 3
    ((24.0, -3.0, 6.0, -3.0), "mixte"),               # ACAD_ISO08W100 : 6 < 24 / 2
    ((1.27, -0.254), "tirets"),                       # DASHED
    ((12.0, -3.0), "tirets"),                         # ACAD_ISO02W100
    ((12.0, -18.0), "tirets"),                        # ACAD_ISO03W100 : 12 > 0,2 × 18
    ((0.0, -0.508), "points"),                        # DOT
    ((0.5, -3.0), "points"),                          # ACAD_ISO07W100
])
def test_la_classe_d_un_motif_se_lit_sur_ses_elements(elements, classe):
    assert classe_de_motif(elements) == classe


def test_toute_la_bibliotheque_standard_est_classee(plan):
    attendues = {"CONTINUOUS": "continu", "BYLAYER": "continu", "BYBLOCK": "continu",
                 "CENTER": "mixte", "CENTER2": "mixte", "CENTERX2": "mixte",
                 "DASHDOT": "mixte", "DIVIDE": "mixte", "PHANTOM": "mixte",
                 "DASHED": "tirets", "DASHED2": "tirets", "DOT": "points", "DOTX2": "points"}
    for nom, classe in attendues.items():
        assert plan.types_de_ligne[nom].classe == classe, nom
    centre = plan.types_de_ligne["CENTER"]
    assert centre.nom == "CENTER" and centre.longueur == pytest.approx(5.08)
    assert centre.elements == pytest.approx((3.175, -0.635, 0.635, -0.635))
    assert not centre.complexe


def test_la_classe_ne_depend_jamais_du_nom(plan):
    """LT07 porte le motif de CENTER sous un nom qui ne dit rien."""
    renomme, centre = plan.types_de_ligne["LT07"], plan.types_de_ligne["CENTER"]
    assert renomme.elements == pytest.approx(centre.elements)
    assert renomme.classe == centre.classe == "mixte"
    for nom, motif in MOTIFS_N1.items():
        assert plan.types_de_ligne[nom].elements == pytest.approx(tuple(motif[1:]))


def test_un_type_de_ligne_complexe_est_dit_complexe(plan):
    gaz = plan.types_de_ligne["GAZ_FICTIF"]
    assert gaz.complexe and gaz.classe == "tirets"


def test_le_motif_se_lit_par_le_type_de_ligne_effectif(plan):
    axe = next(s for s in plan.segments if s.calque == "AXES")
    assert axe.type_ligne == "LT07" and plan.motif_de(axe.type_ligne).classe == "mixte"
    assert plan.motif_de(_segment(plan, -4000).type_ligne).classe == "tirets"   # BYLAYER
    assert plan.motif_de(_segment(plan, -5000).type_ligne).classe == "points"   # entité
    byblock = _segment(plan, -5500, bloc="B_TRAIT")                              # BYBLOCK
    assert byblock.type_ligne == "DASHDOT" and plan.motif_de("dashdot").classe == "mixte"
    assert plan.motif_de("INEXISTANT") is None


# ======================================================== F2 — remplissage
def test_le_remplissage_dit_plein_motif_ou_rien(plan):
    poteaux = [c for c in plan.contours if c.calque == "C001" and c.origine == "hachure"]
    assert len(poteaux) == 9
    assert {(c.remplissage, c.motif_hachure) for c in poteaux} == {("plein", "SOLID")}

    def a(x: float) -> list:
        return [c for c in plan.contours if c.calque == "C002"
                and abs(min(p[0] for p in c.points) - x) < 1e-6]

    (ansi,) = a(0)
    assert (ansi.origine, ansi.rempli, ansi.remplissage, ansi.motif_hachure) == (
        "hachure", True, "motif", "ANSI31")
    (solide,) = a(1000)
    assert (solide.origine, solide.remplissage, solide.motif_hachure) == ("solide", "plein", None)
    (pleine,) = a(2000)
    assert (pleine.remplissage, pleine.motif_hachure) == ("plein", "SOLID")
    # UNE MPOLYGON NON REMPLIE porte le nom « SOLID » : le nom est cité, pas cru.
    (vide,) = a(3000)
    assert (vide.rempli, vide.remplissage, vide.motif_hachure) == (True, None, "SOLID")
    assert {c.remplissage for c in plan.contours if c.origine == "polyligne"} == {None}


# ========================================================= F3 — multilignes
def _multiligne(plan: PrimitivesDxf, x: float, y: float):
    (trouvee,) = [m for m in plan.multilignes
                  if math.dist(m.sommets[0], (x, y)) < 1e-6]
    return trouvee


@pytest.mark.parametrize(("y", "justification", "decalages"), [
    (20000, "haut", (0.0, -200.0)), (21000, "zero", (100.0, -100.0)),
    (22000, "bas", (200.0, 0.0))])
def test_une_multiligne_donne_ses_elements_dans_le_repere_du_dessin(plan, y, justification,
                                                                     decalages):
    m = _multiligne(plan, 0.0, y)
    assert m.justification == justification and m.echelle == 200.0 and not m.ferme
    assert m.decalages == pytest.approx(decalages)
    assert m.epaisseur == pytest.approx(200.0)
    assert m.sommets == ((0.0, y), (5000.0, y))
    for trace, d in zip(m.elements, decalages, strict=True):
        assert [p[1] for p in trace] == pytest.approx([y + d, y + d])
    assert m.remplie is False and m.calque == "C001" and m.couleur == "aci:3"


def test_une_multiligne_fermee_est_dite_fermee(plan):
    m = next(m for m in plan.multilignes if m.ferme)
    assert m.echelle == 250.0 and m.epaisseur == pytest.approx(250.0)
    assert len(m.sommets) == len(m.elements[0]) == 4


def test_une_multiligne_de_bloc_tourne_et_mis_a_l_echelle_est_corrigee(plan):
    """ezdxf garde le facteur 100 d'origine quand l'insertion est tournée : le
    lecteur le porte à 100 × 2 et ramène les tracés à cette échelle."""
    m = _multiligne(plan, 14000.0, 20000.0)
    assert m.source.blocs == ("B_MUR",)
    assert [c for p in m.sommets for c in p] == pytest.approx([14000, 20000, 14000, 22000])
    assert m.echelle == pytest.approx(200.0)
    assert m.decalages == pytest.approx((0.0, -200.0))
    assert [p[0] for p in m.elements[1]] == pytest.approx([14200.0, 14200.0])


def test_une_insertion_non_uniforme_ne_dit_pas_l_epaisseur(plan):
    m = _multiligne(plan, 16000.0, 20000.0)
    assert m.source.blocs == ("B_MUR",)
    assert (m.echelle, m.decalages, m.elements, m.epaisseur) == (None, None, None, None)
    assert len(m.sommets) == 2


def test_une_multiligne_reste_comptee_non_lue_et_rien_ne_l_interprete():
    analyse = parse_document(dxf_information_n1())
    prims = analyse.primitives_dxf
    # 4 à plat + 2 copies de bloc ; celle du calque gelé n'est pas lue.
    assert len(prims.multilignes) == 6
    assert prims.ecartees["entite non lue: MLINE"] == 6
    assert prims.ecartees["calque eteint ou gele: C005"] == 1
    poignees = {m.source.poignee for m in prims.multilignes}
    structure = extract_engineering_data(analyse).structure
    cites = {h for cle in ("walls", "beams", "columns", "piles")
             for element in structure[cle] for h in element["evidence"]["handles"]}
    assert not poignees & cites


# ==================================================== F4 — définitions de blocs
def test_chaque_definition_placee_est_decrite_et_comptee(plan):
    d = plan.definitions
    assert d["B_BULLE"] == DefinitionDeBloc("B_BULLE", False, False, False,
                                            {"CIRCLE": 1, "ATTDEF": 1}, 1, 0, 3, 3)
    # MINSERT 2 × 3, une copie imbriquée, une copie en miroir.
    assert (d["B_SECTION"].insertions, d["B_SECTION"].copies, d["B_SECTION"].fermes) == (3, 8, 1)
    assert (d["B_EXTERIEUR"].types, d["B_EXTERIEUR"].copies) == ({"INSERT": 1}, 1)
    assert (d["B_MUR"].types, d["B_MUR"].insertions) == ({"MLINE": 1}, 2)
    (anonyme,) = [f for f in d.values() if f.nom.startswith("*U")]
    assert anonyme.anonyme and anonyme.types == {"CIRCLE": 1}
    xref, superposee = d["XREF_FOND"], d["XREF_SUPERPOSEE"]
    assert (xref.xref, xref.superposee, xref.insertions, xref.copies) == (True, False, 1, 0)
    assert (superposee.xref, superposee.superposee, superposee.copies) == (False, True, 0)
    # LES COMPTES SONT CEUX DES INSERT LUS : ceux des primitives, xréf en plus.
    for nom in ("B_BULLE", "B_SECTION", "B_MUR", "B_TRAIT"):
        assert d[nom].insertions == sum(1 for i in plan.insertions if i.nom_bloc == nom)


# ===================================================== F5 — échelle d'insertion
def test_l_echelle_d_une_insertion_est_lue_et_composee(plan):
    def echelles(nom: str) -> set:
        return {i.echelle for i in plan.insertions if i.nom_bloc == nom}

    assert echelles("B_BULLE") == {(1.0, 1.0)}
    assert echelles("B_MUR") == {(2.0, 2.0), (2.0, 3.0)}
    # Imbriquée : 2 × 1,5 ; en miroir : (2, -1) ; le MINSERT : (1, 1).
    assert echelles("B_SECTION") == {(1.0, 1.0), (3.0, 3.0), (2.0, -1.0)}


# =========================================================== F6 — calques
def test_un_calque_dit_sa_couleur_et_sa_dependance_d_une_xref(plan):
    c = plan.calques
    assert c["FOND_FICTIF|C006"].depend_xref
    assert not any(info.depend_xref for nom, info in c.items() if nom != "FOND_FICTIF|C006")
    assert (c["AXES"].couleur, c["C001"].couleur, c["C002"].couleur) == (
        "aci:1", "aci:3", "rvb:#0A141E")
    # ÉTEINT, sa couleur est négative dans le DXF : sa valeur absolue.
    assert c["C004"].eteint and c["C004"].couleur == "aci:6"


# ========================================================= F7 — couleurs
@pytest.mark.parametrize(("y", "bloc", "couleur"), [
    (-10000, None, "aci:2"),            # ACI de l'entité
    (-10100, None, "rvb:#FF0000"),      # couleur vraie (code 420)
    (-10200, None, "rvb:#0A141E"),      # BYLAYER : la couleur vraie du calque
    (-10300, None, "aci:7"),            # BYBLOCK hors bloc
    (-10400, None, "aci:7"),            # calque absent de la table
    (-11000, "B_COULEURS", "aci:6"),    # BYBLOCK : l'INSERT
    (-10990, "B_COULEURS", "rvb:#0A141E"),  # BYLAYER sur 0 : le calque de l'INSERT
    (-10980, "B_COULEURS", "aci:3"),    # BYLAYER sur son propre calque
])
def test_la_couleur_est_resolue_par_les_regles_du_dao(plan, y, bloc, couleur):
    assert _segment(plan, y, bloc=bloc).couleur == couleur


def test_toutes_les_primitives_ont_une_couleur_et_les_insertions_aussi(plan):
    toutes = (plan.segments + plan.contours + plan.cercles + plan.textes + plan.insertions
              + plan.multilignes)
    assert all(p.couleur is not None for p in toutes)
    assert {i.couleur for i in plan.insertions if i.nom_bloc == "B_COULEURS"} == {"aci:6"}
    assert plan.n1_incidents == {}


# ====================================================== invariance (I1 à I6)
def test_les_champs_n1_ne_participent_pas_a_l_egalite():
    source = Source("1", "LINE")
    rouge = Segment("0", "CONTINUOUS", source, (0.0, 0.0), (1.0, 0.0), couleur="aci:1")
    bleu = Segment("0", "CONTINUOUS", source, (0.0, 0.0), (1.0, 0.0), couleur="aci:5")
    assert rouge == bleu and hash(rouge) == hash(bleu)
    assert dataclasses.replace(rouge, couleur=None) == rouge


def test_les_listes_n1_ne_comptent_pas_dans_la_borne(plan):
    sans = dataclasses.replace(plan, multilignes=[], definitions={}, types_de_ligne={})
    assert plan.nombre() == sans.nombre() and plan.multilignes


def _sorties(octets: bytes) -> str:
    """Tout ce que le produit sort, dans l'ordre : comme le balayage de G1."""
    def canon(o):  # noqa: ANN001, ANN202
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return {f.name: canon(getattr(o, f.name)) for f in dataclasses.fields(o)
                    if f.name not in ("octets", "primitives_dxf")}
        if isinstance(o, dict):
            return {str(k): canon(v) for k, v in o.items()}
        if isinstance(o, list | tuple):
            return [canon(x) for x in o]
        if isinstance(o, float) and not math.isfinite(o):
            return repr(o)
        return o

    analyse = parse_document(octets)
    return json.dumps([canon(analyse), canon(extract_engineering_data(analyse))],
                      ensure_ascii=False)


def _sans_n1(monkeypatch: pytest.MonkeyPatch) -> None:
    lecteur = module_primitives._Lecteur
    monkeypatch.setattr(module_primitives, "_motifs_de_ligne", lambda document, incident: {})
    monkeypatch.setattr(lecteur, "_couleur", lambda self, *args: None)
    monkeypatch.setattr(lecteur, "_multiligne", lambda self, *args: None)
    monkeypatch.setattr(lecteur, "_echelle", lambda self, entite: None)
    monkeypatch.setattr(lecteur, "_definition", lambda self, nom, definition: DefinitionDeBloc(
        nom, False, False, False, {}, 0, 0))


@pytest.mark.parametrize("fabrique", [dxf_information_n1, dxf_fondations_pieux])
def test_neutraliser_la_lecture_n1_ne_change_aucune_sortie(monkeypatch, fabrique):
    octets = fabrique()
    avec = _sorties(octets)
    _sans_n1(monkeypatch)
    sans = _sorties(octets)
    prims = parse_document(octets).primitives_dxf
    assert prims.types_de_ligne == {} and prims.multilignes == []
    assert avec == sans


def test_une_information_n1_illisible_est_comptee_et_ne_change_rien(monkeypatch):
    octets = dxf_information_n1()
    avant = _sorties(octets)

    def illisible(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise ValueError("FICTIF")

    monkeypatch.setattr(module_primitives, "classe_de_motif", illisible)
    monkeypatch.setattr(module_primitives, "Multiligne", illisible)
    monkeypatch.setattr(module_primitives, "_code_couleur", illisible)
    prims = parse_document(octets).primitives_dxf
    assert prims.types_de_ligne == {} and prims.multilignes == []
    assert prims.n1_incidents["type de ligne illisible"] == 28
    assert prims.n1_incidents["multiligne illisible"] == 6
    assert prims.n1_incidents["couleur ou drapeaux de calque illisibles"] == len(prims.calques)
    assert "entite illisible: MLINE" not in prims.ecartees
    assert _sorties(octets) == avant


def test_une_feuille_pdf_n_a_pas_d_information_n1():
    from fabrique_pdf_vectoriel import pdf_plan_vectoriel

    prims = parse_document(pdf_plan_vectoriel(), ocr=None).primitives_dxf
    assert prims.segments and prims.types_de_ligne == {} and prims.multilignes == []
    assert prims.definitions == {} and prims.n1_incidents == {}
    assert {s.couleur for s in prims.segments} == {None}
    assert {c.remplissage for c in prims.contours} == {None}
