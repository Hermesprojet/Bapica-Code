"""Le repli d'un mot plus large que sa colonne, dans l'ecrivain PDF.

MESURE LE 16/09 SUR LA NOTE A CINQ CHAPITRES, RASTERISEE (`pdftoppm`, 150 dpi,
page 2): dans la colonne « Symbole », « EN 1992-1-1:gamma_C_persistent »
debordait sur la colonne « Description », et le symbole recouvrait « beton ».
Ni l'un ni l'autre ne se lisait plus. La regle « un mot trop large n'est pas
coupe » protegeait les identifiants d'une coupe au milieu; elle laissait deux
colonnes s'ecrire l'une sur l'autre.

Ce que ce module etablit: un mot trop large se coupe APRES ses separateurs de
nom, jamais ailleurs; un atome sans separateur — une empreinte — continue de
deborder plutot que d'etre coupe au milieu. Aucune base, aucun document: la
fonction de repli, mesuree avec la metrique Helvetica de la specification PDF.
"""

from __future__ import annotations

from eurostruct_api.pdf import HELVETICA, MARGE, PAGE_L, _largeur, _replier

#: La largeur d'une cellule du tableau a cinq colonnes de la note, telle que
#: `composer_pdf` la calcule: (utile / 5) - 6, en corps 8.5.
CORPS = 8.5
CELLULE = (PAGE_L - 2 * MARGE) / 5 - 6


def _aucune_ligne_ne_deborde(lignes: list[str]) -> None:
    for ligne in lignes:
        assert _largeur(ligne, HELVETICA, CORPS) <= CELLULE, (
            f"« {ligne} » deborde de la cellule ({_largeur(ligne, HELVETICA, CORPS):.1f} "
            f"> {CELLULE:.1f} pt)")


def test_le_symbole_mesure_le_16_09_ne_recouvre_plus_la_colonne_voisine() -> None:
    lignes = _replier("EN 1992-1-1:gamma_C_persistent", HELVETICA, CORPS, CELLULE)
    _aucune_ligne_ne_deborde(lignes)
    #: LE NOM SE RECOMPOSE SANS AMBIGUITE: la coupe est tombee apres « : », et
    #: le separateur reste en fin de ligne.
    assert lignes == ["EN 1992-1-1:", "gamma_C_persistent"]
    assert "".join(lignes).replace(":", ": ", 1) == "EN 1992-1-1: gamma_C_persistent"


def test_un_nom_a_points_et_soulignes_se_coupe_apres_ses_separateurs() -> None:
    lignes = _replier("be.ec2.nu_strength_reduction", HELVETICA, CORPS, CELLULE)
    _aucune_ligne_ne_deborde(lignes)
    assert len(lignes) >= 2
    #: CHAQUE LIGNE SAUF LA DERNIERE FINIT PAR UN SEPARATEUR, et la
    #: concatenation rend le nom exact.
    for ligne in lignes[:-1]:
        assert ligne[-1] in ":_./-", ligne
    assert "".join(lignes) == "be.ec2.nu_strength_reduction"


def test_une_empreinte_sans_separateur_n_est_pas_coupee_au_milieu() -> None:
    """Le comportement d'avant, garde la ou il est juste."""
    empreinte = "0" * 64
    assert _replier(empreinte, HELVETICA, CORPS, CELLULE) == [empreinte]


def test_un_mot_qui_tient_n_est_jamais_coupe_meme_avec_separateurs() -> None:
    assert _replier("EN 1992-1-1 §6.1", HELVETICA, CORPS, CELLULE) == ["EN 1992-1-1 §6.1"]
    assert _replier("f_ck", HELVETICA, CORPS, CELLULE) == ["f_ck"]


def test_le_repli_aux_espaces_est_inchange() -> None:
    lignes = _replier("Coefficient partiel du beton, situations durables et transitoires",
                      HELVETICA, CORPS, CELLULE)
    _aucune_ligne_ne_deborde(lignes)
    assert " ".join(lignes) == (
        "Coefficient partiel du beton, situations durables et transitoires")
