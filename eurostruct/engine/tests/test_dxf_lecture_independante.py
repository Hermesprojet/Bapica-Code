"""Le DXF relu SANS ezdxf, par un analyseur qui ne partage aucune ligne avec lui.

POURQUOI CE FICHIER EXISTE A COTE DE `test_dxf.py`
---------------------------------------------------
`test_dxf.py` ecrit avec ezdxf, relit avec ezdxf, et fait passer l'auditeur
d'ezdxf. C'est utile, et ce n'est pas une preuve d'interoperabilite: une
convention que la bibliotheque applique en ecriture, elle la comprend en
lecture. Les defauts qui font refuser un fichier par AutoCAD ou LibreCAD sont
precisement ceux qu'un aller-retour dans une seule implementation ne peut pas
voir — un handle en double, un calque reference et jamais defini, un
`$HANDSEED` depasse, un style de cotation qui pointe vers un handle absent.

L'analyseur ci-dessous lit le flux de paires code/valeur **tel que la norme le
decrit**, en une cinquantaine de lignes, sans importer ezdxf. Ce qu'il
constate, il le constate sur les octets.

CE QUE CES CAS NE PROUVENT PAS, ET IL FAUT LE DIRE
----------------------------------------------------
Ils ne remplacent pas l'ouverture du fichier dans un AutoCAD reel. Aucun
logiciel de CAO n'a tourne ici. Ils ferment la classe de defauts qu'un
aller-retour ezdxf laisse passer, et rien de plus: un fichier qui passe ces
cas peut encore deplaire a l'ecran — echelle de trace, lisibilite des cotes,
epaisseurs. Ces trois-la se jugent a l'oeil, sur un poste, et restent a faire.
"""

from __future__ import annotations

import pytest

from eurostruct_engine.drawing import BarRow, BeamSectionSpec, build_beam_section

# --------------------------------------------------------------------------
# L'ANALYSEUR. Aucun import d'ezdxf ici, et c'est tout l'interet.
# --------------------------------------------------------------------------

#: Les codes qui portent un HANDLE d'objet dans un enregistrement.
#: `5` partout, sauf les entrees de la table DIMSTYLE qui utilisent `105` —
#: parce que `5` y designerait le style lui-meme dans les versions anciennes.
CODES_DE_HANDLE = ("5", "105")


def paires(texte: str) -> list[tuple[str, str]]:
    """Le flux DXF est une suite stricte de deux lignes: un code, une valeur.

    Un fichier dont le nombre de lignes est impair, ou dont une ligne de code
    n'est pas un entier, n'est pas un DXF — et aucun logiciel de CAO n'ira
    plus loin.
    """
    lignes = texte.split("\n")
    if lignes and lignes[-1] == "":
        lignes.pop()
    assert len(lignes) % 2 == 0, (
        f"le fichier porte {len(lignes)} lignes: le flux code/valeur ne peut "
        "pas etre impair.")
    sortie = []
    for i in range(0, len(lignes), 2):
        code = lignes[i].strip()
        assert code.lstrip("-").isdigit(), (
            f"ligne {i + 1}: « {lignes[i]!r} » n'est pas un code de groupe.")
        sortie.append((code, lignes[i + 1]))
    return sortie


def enregistrements(flux: list[tuple[str, str]]) -> list[tuple[str, dict]]:
    """Decoupe le flux en enregistrements: chacun commence a un code 0.

    Les valeurs repetees (plusieurs `100`, plusieurs `330`) sont conservees en
    liste sous la meme cle: un dictionnaire qui les ecraserait cacherait
    justement les chaines de reference qu'on veut suivre.
    """
    sortie: list[tuple[str, dict]] = []
    courant: dict[str, list[str]] | None = None
    for code, valeur in flux:
        if code == "0":
            courant = {}
            sortie.append((valeur, courant))
        elif courant is not None:
            courant.setdefault(code, []).append(valeur)
    return sortie


def sections(flux: list[tuple[str, str]]) -> dict[str, list[tuple[str, str]]]:
    """Les sections, par nom, avec leur contenu — et le controle de fermeture.

    Une section non fermee, ou une section ouverte dans une autre, est un
    fichier tronque: la plupart des lecteurs s'arretent la, en silence et en
    n'affichant que ce qu'ils ont eu le temps de lire.
    """
    trouvees: dict[str, list[tuple[str, str]]] = {}
    nom: str | None = None
    debut = 0
    for i, (code, valeur) in enumerate(flux):
        if code == "0" and valeur == "SECTION":
            assert nom is None, f"section ouverte dans « {nom} » non fermee."
            assert flux[i + 1][0] == "2", "une SECTION sans code 2 n'a pas de nom."
            nom, debut = flux[i + 1][1], i + 2
        elif code == "0" and valeur == "ENDSEC":
            assert nom is not None, "ENDSEC sans SECTION ouverte."
            trouvees[nom] = flux[debut:i]
            nom = None
    assert nom is None, f"la section « {nom} » n'est jamais fermee."
    return trouvees


def entete(flux_entete: list[tuple[str, str]]) -> dict[str, str]:
    """Les variables d'entete: un code 9 nomme, la paire suivante porte la valeur."""
    variables: dict[str, str] = {}
    for i, (code, valeur) in enumerate(flux_entete):
        if code == "9" and i + 1 < len(flux_entete):
            variables[valeur] = flux_entete[i + 1][1]
    return variables


# --------------------------------------------------------------------------
# Le fichier soumis a l'analyseur
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def octets(tmp_path_factory) -> str:
    """Un cas representatif: section de poutre ferraillee, cotee, avec cartouche."""
    spec = BeamSectionSpec(
        b=300.0, h=600.0, cover=30.0, link_diameter=8.0,
        bottom=(BarRow(count=4, diameter=20, mark="A1", length=6200),),
        top=(BarRow(count=2, diameter=12, mark="A2", length=6200),),
        link_spacing=200, plot_scale=20,
        title="COUPE", element="P1", project="LECTURE INDEPENDANTE",
        concrete_grade="C30/37", steel_grade="B500B", exposure_class="XC1",
        date="2026-09-14",
    )
    doc, _ = build_beam_section(spec)
    chemin = tmp_path_factory.mktemp("dxf") / "coupe.dxf"
    doc.saveas(chemin)
    # LU EN UTF-8 STRICT: un DXF R2018 est encode en UTF-8, et un octet
    # invalide ferait echouer la lecture ici avant toute autre verification.
    return chemin.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def flux(octets):
    return paires(octets)


# --------------------------------------------------------------------------
# La forme du fichier
# --------------------------------------------------------------------------

def test_le_flux_se_termine_par_eof(flux):
    """Sans `0/EOF`, un lecteur strict considere le fichier tronque."""
    assert flux[-1] == ("0", "EOF")


def test_les_six_sections_sont_presentes_et_fermees(flux):
    """`sections()` leve des qu'une section reste ouverte ou s'imbrique."""
    trouvees = sections(flux)
    assert set(trouvees) == {
        "HEADER", "CLASSES", "TABLES", "BLOCKS", "ENTITIES", "OBJECTS"}


def test_la_version_et_l_unite_sont_lues_sur_les_octets(flux):
    """R2018 et millimetres, constates dans l'entete, pas demandes a ezdxf.

    `$INSUNITS = 4` est ce qui fait qu'un trait de 300 unites mesure 300 mm et
    non 300 pouces a l'import. Une valeur absente ou nulle laisse le logiciel
    de CAO choisir, et il choisit selon SON gabarit.
    """
    variables = entete(sections(flux)["HEADER"])
    assert variables["$ACADVER"] == "AC1032"
    assert variables["$INSUNITS"] == "4"


# --------------------------------------------------------------------------
# Les references, suivies a la main
# --------------------------------------------------------------------------

def _handles(flux) -> list[str]:
    vus = []
    for typologie, champs in enregistrements(flux):
        if typologie in ("SECTION", "ENDSEC", "EOF"):
            continue
        for code in CODES_DE_HANDLE:
            if code in champs:
                vus.append(champs[code][0])
                break
    return vus


def test_aucun_handle_n_est_en_double(flux):
    """Un handle duplique est un refus net cote AutoCAD.

    ezdxf les attribue par compteur et n'en produit pas: le cas ne vaut donc
    pas contre la bibliotheque, il vaut contre NOS ajouts — un bloc copie, un
    cartouche insere deux fois, un correctif qui reecrit un enregistrement.
    """
    vus = _handles(flux)
    doubles = {h for h in vus if vus.count(h) > 1}
    assert not doubles, f"handles en double: {sorted(doubles)}"


def test_le_handseed_depasse_tous_les_handles(flux):
    """`$HANDSEED` annonce le prochain handle libre.

    S'il est inferieur ou egal a un handle deja pris, le premier objet cree a
    l'ouverture ecrase un objet existant. AutoCAD le signale; d'autres le font
    en silence.
    """
    graine = int(entete(sections(flux)["HEADER"])["$HANDSEED"], 16)
    plus_grand = max(int(h, 16) for h in _handles(flux))
    assert graine > plus_grand, (
        f"$HANDSEED = {graine:X} mais le plus grand handle utilise est "
        f"{plus_grand:X}.")


def test_tout_calque_dessine_est_defini_dans_la_table(flux):
    """Le defaut classique: l'entite cite un calque que la table n'a pas.

    Le fichier s'ouvre quand meme — et tout se retrouve sur le calque 0, sans
    couleur ni epaisseur. Le plan reste « lisible » et devient faux a
    l'impression.
    """
    trouvees = sections(flux)
    definis = {champs["2"][0]
               for typologie, champs in enregistrements(trouvees["TABLES"])
               if typologie == "LAYER" and "2" in champs}
    utilises: set[str] = set()
    for section in ("ENTITIES", "BLOCKS"):
        for code, valeur in trouvees[section]:
            if code == "8":
                utilises.add(valeur)
    assert utilises, "aucune entite ne porte de calque: le plan serait vide."
    assert utilises <= definis, (
        f"calques cites et jamais definis: {sorted(utilises - definis)}")


def test_le_style_de_cotation_pointe_vers_un_style_de_texte_existant(flux):
    """La chaine DIMSTYLE -> (code 340) -> STYLE, suivie par handle.

    C'est le chemin qu'un logiciel de CAO emprunte pour savoir avec quelle
    police ecrire une cote. Un handle qui ne resout pas donne une cote sans
    texte, ou du texte a la police du gabarit local: deux plans differents
    pour deux lecteurs.
    """
    tables = sections(flux)["TABLES"]
    styles = {champs["5"][0]: champs["2"][0]
              for typologie, champs in enregistrements(tables)
              if typologie == "STYLE" and "5" in champs and "2" in champs}
    cotations = {champs["2"][0]: champs.get("340", [None])[0]
                 for typologie, champs in enregistrements(tables)
                 if typologie == "DIMSTYLE" and "2" in champs}
    assert "EUROSTRUCT" in cotations, (
        f"le style de cotation du produit est absent: {sorted(cotations)}")
    vise = cotations["EUROSTRUCT"]
    assert vise in styles, (
        f"EUROSTRUCT pointe le handle {vise}, absent de la table STYLE.")


def test_toute_cote_dessinee_cite_un_style_declare(flux):
    """Une DIMENSION nomme son style au code 3. Il doit exister.

    Sinon la cote s'affiche au style courant du poste qui ouvre le fichier:
    la valeur reste juste, sa presentation change d'un lecteur a l'autre, et
    c'est une cote de plan d'execution.
    """
    trouvees = sections(flux)
    declares = {champs["2"][0]
                for typologie, champs in enregistrements(trouvees["TABLES"])
                if typologie == "DIMSTYLE" and "2" in champs}
    cites = {champs["3"][0]
             for typologie, champs in enregistrements(trouvees["ENTITIES"])
             if typologie == "DIMENSION" and "3" in champs}
    assert cites, "aucune cote sur le plan."
    assert cites <= declares, (
        f"styles de cotation cites et non declares: {sorted(cites - declares)}")
