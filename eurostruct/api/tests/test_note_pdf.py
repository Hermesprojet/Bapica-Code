"""La note de calcul en PDF : lisible par un tiers, stable, sans perte.

LE LECTEUR EST INDEPENDANT, ET C'EST TOUT L'INTERET. Verifier un PDF avec le
code qui l'a ecrit ne prouve pas qu'il est valide: cela prouve qu'il est
coherent avec lui-meme. `pypdf` n'a pas ete ecrit ici, ne connait pas nos
conventions, et refuse un fichier mal forme — c'est le meme role de temoin que
le client S3 brut joue dans `test_stockage_s3.py`.

CE MODULE NE DEMANDE NI BASE NI RESEAU. La composition est une fonction pure:
des donnees relues d'un cote, des octets de l'autre.
"""
from __future__ import annotations

import io
from html import unescape

import pytest

from eurostruct_api.note import MEDIA_TYPE_PDF, rendre_note, rendre_note_pdf
from eurostruct_api.pdf import (
    CaractereNonRepresentable,
    Champs,
    Paragraphe,
    Tableau,
    Titre,
    composer_pdf,
)

#: ON SAUTE PAR MARQUEUR, PAS AU NIVEAU DU MODULE.
#:
#: `pytest.importorskip` en tete de fichier leve pendant la COLLECTE: les
#: quatorze cas disparaissent purement du decompte, et `run_tests.sh` — qui
#: compare collectes et executes precisement pour reperer ce genre de
#: disparition — a mesure « 332 collectes, 333 executes ». Un module entier
#: s'etait volatilise, et seul cet ecart d'une unite le disait.
#:
#: Avec un marqueur, les quatorze cas restent COLLECTES et se declarent
#: ignores un par un. L'absence du temoin devient visible au lieu d'etre
#: silencieuse.
try:
    import pypdf
except ImportError:  # pragma: no cover — depend de l'environnement
    pypdf = None

pytestmark = pytest.mark.skipif(
    pypdf is None,
    reason=("`pypdf` est le LECTEUR TEMOIN de ces cas: sans lui, on ne "
            "verifierait le PDF qu'avec le code qui l'a ecrit. "
            "Installer: pip install -e 'eurostruct/api[dev]'"))

NOTICE = ("Ce document ne vaut pas validation. Aucun logiciel ne signe une "
          "note de calcul: un ingenieur habilite doit la relire et l'attester.")
MENTION = "PROJET — NON SIGNABLE"

PROJET = {
    "project_id": "11111111-1111-1111-1111-111111111111",
    "organization_id": "22222222-2222-2222-2222-222222222222",
    "organization_name": "FICTIF Bureau d'études",
    "name": "FICTIF Halle métallique",
    "reference": "FICTIF-2026-01",
    "country": "BE",
    "region": "Wallonie",
    "ndp_as_of": "2024-01-15",
}

CALCUL = {
    "calculation_id": "33333333-3333-3333-3333-333333333333",
    "created_at": "2026-08-31T10:00:00+00:00",
    "status": "succeeded",
    "strict_ndp": False,
    "engine_version": "0.3.0",
    "engine_build_sha": "b" * 40,
    "inputs_hash": "c" * 64,
    "execution_identity": "d" * 64,
    "ndp_as_of": "2024-01-15",
    "request": {
        "element": "poutre P1",
        "situation": "persistent",
        "section": {"b": {"value": 300.0, "unit": "mm"},
                    "h": {"value": 600.0, "unit": "mm"},
                    "d": {"value": 550.0, "unit": "mm"}},
        "materials": {"concrete_grade": "C30/37", "steel_grade": "B500B"},
        "M_Ed": {"value": 250.0, "unit": "kNm"},
    },
    "result": {
        "result": {
            "As_required": {"value": 1345.0, "unit": "mm2"},
            "M_Rd": {"value": 268.4, "unit": "kNm"},
            "mu": 0.0918,
            "xi": 0.1204,
            "eps_s": 0.0154,
            "utilisation": 0.9315,
        },
        "verification": {
            "checks": [
                {"name": "Flexion ELU", "status": "pass", "utilisation": 0.9315,
                 "acting": "250,0 kNm", "resisting": "268,4 kNm",
                 "clause": {"cite": "EN 1992-1-1 §6.1"}},
            ],
            "max_utilisation": 0.9315,
        },
    },
    "journal": {
        "title": "Flexion simple, section rectangulaire",
        "steps": [
            {"symbol": "μ", "description": "Moment réduit",
             "numeric": "250e6 / (300 × 550² × 20)", "formatted": "0,0918",
             "clause": {"cite": "EN 1992-1-1 §6.1"}},
            {"symbol": "ξ", "description": "Hauteur réduite d'axe neutre",
             "numeric": "1,25 × (1 - √(1 - 2μ))", "formatted": "0,1204",
             "clause": {"cite": "EN 1992-1-1 §6.1"}},
        ],
        "clauses": ["EN 1992-1-1 §6.1", "EN 1992-1-1 §9.2.1.1"],
    },
    "ndp_snapshot": {
        "country": "BE", "region": "Wallonie", "as_of": "2024-01-15",
        "strict": False,
        "annexes": [
            {"reference": "EN 1992-1-1 ANB", "edition": "2016",
             "effective_from": "2016-04-01",
             "source_official": "FICTIF — non confirmé"},
        ],
        "unverified": ["alpha_cc", "gamma_c"],
    },
}


def _texte(octets: bytes) -> str:
    lecteur = pypdf.PdfReader(io.BytesIO(octets))
    return "\n".join(page.extract_text() for page in lecteur.pages)


def _pages(octets: bytes) -> int:
    return len(pypdf.PdfReader(io.BytesIO(octets)).pages)


# ===========================================================================
# 1 — C'EST UN PDF, ET UN TIERS SAIT L'OUVRIR
# ===========================================================================
def test_le_document_est_un_pdf_qu_un_lecteur_tiers_ouvre():
    octets = rendre_note_pdf(PROJET, CALCUL, notice=NOTICE, mention=MENTION)

    assert octets.startswith(b"%PDF-"), "l'en-tete PDF manque"
    assert octets.rstrip().endswith(b"%%EOF"), "la fin de fichier manque"
    assert _pages(octets) >= 1
    assert MEDIA_TYPE_PDF == "application/pdf"


def test_le_document_tient_sur_plusieurs_pages_sans_perdre_la_fin():
    """LA PAGINATION EST LA OU UN RENDU MAISON SE CASSE.

    Un bloc qui deborde sans creer de page laisse du texte ecrit SOUS la marge
    — invisible a l'ecran, absent a l'impression, et parfaitement silencieux.
    On compose donc un document franchement long et on exige que sa DERNIERE
    section soit encore lisible.
    """
    long_calcul = dict(CALCUL)
    long_calcul["journal"] = {
        "title": "Journal volontairement long",
        "steps": [
            {"symbol": f"s{i}", "description": f"Étape numéro {i}",
             "numeric": f"{i} × 2", "formatted": f"{i * 2}",
             "clause": {"cite": "EN 1992-1-1 §6.1"}}
            for i in range(120)
        ],
        "clauses": [],
    }
    octets = rendre_note_pdf(PROJET, long_calcul, notice=NOTICE,
                             mention=MENTION)

    assert _pages(octets) >= 3, "un journal de 120 etapes tient sur une page ?"
    texte = _texte(octets)
    assert "Étape numéro 119" in texte, "la fin du journal a disparu"
    # LA TRACABILITE VIENT APRES LE JOURNAL: si elle manque, c'est que la
    # composition s'est arretee en cours de route.
    assert "Identité d'exécution" in texte
    assert "d" * 64 in texte


# ===========================================================================
# 2 — LES MEMES OCTETS, DEUX FOIS
# ===========================================================================
def test_deux_compositions_du_meme_calcul_rendent_les_memes_octets():
    """L'ADRESSAGE PAR CONTENU L'EXIGE, ET RIEN D'AUTRE NE LE GARANTIT.

    La cle d'un livrable derive de son empreinte. Un generateur qui inscrit
    une date de creation ferait changer cette empreinte a chaque composition,
    alors qu'aucun chiffre du document n'aurait bouge: deux objets dans le
    magasin, deux lignes en base, pour un seul et meme calcul.
    """
    un = rendre_note_pdf(PROJET, CALCUL, notice=NOTICE, mention=MENTION)
    deux = rendre_note_pdf(PROJET, CALCUL, notice=NOTICE, mention=MENTION)

    assert un == deux


def test_aucune_date_n_est_inscrite_dans_les_octets():
    """LA PREUVE DIRECTE, sur les octets plutot que sur le comportement.

    `/CreationDate` et `/ModDate` sont les deux champs qui font varier un PDF
    d'une seconde a l'autre. Leur absence se constate.
    """
    octets = rendre_note_pdf(PROJET, CALCUL, notice=NOTICE, mention=MENTION)

    assert b"/CreationDate" not in octets
    assert b"/ModDate" not in octets
    assert b"/Producer" not in octets


# ===========================================================================
# 3 — CE QUE LE DOCUMENT DOIT DIRE
# ===========================================================================
def test_la_mention_obligatoire_et_le_filigrane_sont_lisibles():
    """INTERDICTION N° 8: aucun document sans la mention de validation."""
    texte = _texte(rendre_note_pdf(PROJET, CALCUL, notice=NOTICE,
                                   mention=MENTION))

    assert "NON SIGNABLE" in texte
    assert "ingenieur habilite" in texte or "ingénieur habilité" in texte
    assert "n'est pas un livrable final" in texte


def test_un_calcul_strict_ne_porte_pas_le_filigrane_mais_garde_la_notice():
    texte = _texte(rendre_note_pdf(PROJET, CALCUL, notice=NOTICE,
                                   mention=None))

    assert "NON SIGNABLE" not in texte
    assert "ne signe une" in texte


def test_les_nombres_enregistres_sont_ceux_qui_s_affichent():
    """INTERDICTION N° 9: on pose la virgule, on ne lisse rien.

    `0,9315` -> `93,1 %`. Pas `93 %`, pas `plus de 90 %`.
    """
    texte = _texte(rendre_note_pdf(PROJET, CALCUL, notice=NOTICE,
                                   mention=MENTION))

    # 0,9315 x 100 = 93,15000...1 -> « 93,2 ». Pas « 93 », pas « plus de
    # 90 % », et pas « 93,1 » non plus: le formatage suit le nombre, dans les
    # deux sens.
    assert "93,2 %" in texte
    assert "1345 mm2" in texte or "1345" in texte
    assert "268,40 kNm" in texte


def test_les_lettres_grecques_survivent_au_document():
    """UNE GRANDEUR N'EST PAS UN ORNEMENT.

    WinAnsi ne porte pas le grec. Sans la police `Symbol`, `μ` et `ξ`
    disparaitraient ou deviendraient des lettres latines — et la note
    afficherait `m` la ou le moteur a ecrit `μ`.
    """
    texte = _texte(rendre_note_pdf(PROJET, CALCUL, notice=NOTICE,
                                   mention=MENTION))

    assert "μ" in texte, "le moment reduit a perdu son symbole"
    assert "ξ" in texte, "la hauteur reduite d'axe neutre a perdu son symbole"
    assert "ε" in texte


def test_les_parametres_non_confirmes_sont_nommes():
    """INTERDICTION N° 2 ET N° 3: ce qui n'est pas confirme se dit."""
    texte = _texte(rendre_note_pdf(PROJET, CALCUL, notice=NOTICE,
                                   mention=MENTION))

    assert "alpha_cc" in texte
    assert "gamma_c" in texte


# ===========================================================================
# 4 — RIEN NE DISPARAIT EN SILENCE
# ===========================================================================
def test_un_caractere_sans_glyphe_fait_lever_au_lieu_de_disparaitre():
    """LE PIRE COMPORTEMENT SERAIT LE PLUS DISCRET.

    Un generateur qui remplace l'inconnu par `?` — ou pire, par rien —
    produirait un document qui a l'air correct et qui affirme autre chose. On
    refuse d'ecrire plutot que d'ecrire faux.
    """
    with pytest.raises(CaractereNonRepresentable) as pris:
        composer_pdf("t", [Paragraphe("un idéogramme: 漢")])

    assert "漢" in str(pris.value)
    assert "U+" in str(pris.value)


def test_les_substitutions_declarees_ne_perdent_pas_de_sens():
    """Espaces insecables, apostrophes typographiques, tirets: remplaces."""
    octets = composer_pdf("t", [Paragraphe("l’essai — 10 000 m² « oui »")])
    texte = _texte(octets)

    assert "l'essai" in texte
    assert "10 000" in texte or "10 000" in texte
    assert "m²" in texte


# ===========================================================================
# 5 — LES DEUX RENDUS NE DOIVENT PAS DIVERGER
# ===========================================================================
def test_les_deux_rendus_portent_les_memes_faits():
    """LA GARDE DE LA DUPLICATION ASSUMEE.

    Le HTML et le PDF sont composes par deux fonctions distinctes, depuis les
    memes donnees relues. C'est un choix — convertir le HTML demanderait un
    moteur de rendu — et sa contrepartie est le risque qu'un fait figure dans
    l'un et pas dans l'autre.

    Ce cas nomme les faits qui doivent etre dans LES DEUX. Il ne compare pas
    les mises en page: il compare ce que les deux documents AFFIRMENT.
    """
    html = rendre_note(PROJET, CALCUL, notice=NOTICE, mention=MENTION)
    texte = _texte(rendre_note_pdf(PROJET, CALCUL, notice=NOTICE,
                                   mention=MENTION))

    faits = [
        PROJET["organization_name"],
        PROJET["name"],
        PROJET["reference"],
        CALCUL["calculation_id"],
        CALCUL["engine_build_sha"],
        CALCUL["inputs_hash"],
        CALCUL["execution_identity"],
        "NON SIGNABLE",
        "alpha_cc",
        "93,2",
    ]
    # ON COMPARE CE QUE LES DOCUMENTS DISENT, PAS LEUR ENCODAGE. Le HTML
    # echappe l'apostrophe de « Bureau d'études »; le PDF ne l'echappe pas.
    # Comparer les octets bruts ferait rougir ce cas sur une difference qui
    # n'en est pas une.
    lisible = unescape(html)
    manquants_html = [f for f in faits if f not in lisible]
    manquants_pdf = [f for f in faits if f not in texte]

    assert not manquants_html, f"absents du HTML: {manquants_html}"
    assert not manquants_pdf, f"absents du PDF: {manquants_pdf}"


# ===========================================================================
# 6 — LES BLOCS, UN PAR UN
# ===========================================================================
def test_les_quatre_blocs_composent_un_document_lisible():
    octets = composer_pdf("Titre du document", [
        Titre("Un titre de niveau 1", 1),
        Paragraphe("Un paragraphe encadré.", encadre=True),
        Champs([("Libellé", "Valeur")]),
        Tableau(["A", "B"], [["gauche", "droite"]], droite={1}),
    ])
    texte = _texte(octets)

    for attendu in ("Un titre de niveau 1", "Un paragraphe encadré",
                    "Libellé", "Valeur", "gauche", "droite"):
        assert attendu in texte, f"« {attendu} » absent du document"


def test_un_document_sans_bloc_reste_un_pdf_valide():
    """LE CAS VIDE N'EST PAS UNE CURIOSITE: c'est ce qu'une erreur produit."""
    octets = composer_pdf("vide", [])

    assert octets.startswith(b"%PDF-")
    assert _pages(octets) == 1


# ===========================================================================
# 7 — LE PIED DE PAGE
# ===========================================================================
def test_chaque_page_porte_son_numero_et_le_total():
    """UNE NOTE FINIT RELIEE DANS UN DOSSIER, ET DES PAGES S'Y PERDENT.

    Sans « sur T », personne ne peut constater qu'il manque la derniere; sans
    le titre, une page detachee n'appartient plus a rien.
    """
    long_calcul = dict(CALCUL)
    long_calcul["journal"] = {
        "title": "Journal long",
        "steps": [{"symbol": f"s{i}", "description": f"Étape {i}",
                   "numeric": f"{i}", "formatted": f"{i}",
                   "clause": {"cite": "EN 1992-1-1 §6.1"}}
                  for i in range(120)],
        "clauses": [],
    }
    octets = rendre_note_pdf(PROJET, long_calcul, notice=NOTICE,
                             mention=MENTION)
    lecteur = pypdf.PdfReader(io.BytesIO(octets))
    total = len(lecteur.pages)
    assert total >= 3

    for numero, page in enumerate(lecteur.pages, start=1):
        texte = page.extract_text()
        assert f"page {numero} sur {total}" in texte, (
            f"la page {numero} ne porte pas son numero")
        # LE TITRE SUR CHAQUE PAGE: une feuille detachee doit dire d'ou elle
        # vient.
        assert "FICTIF Halle" in texte


def test_le_pied_de_page_ne_recouvre_pas_le_contenu():
    """IL VIT SOUS LA ZONE DE COMPOSITION, PAS DEDANS.

    Un pied de page ecrit dans le flux consommerait de la hauteur utile et
    decalerait tout; ecrit trop haut, il passerait SUR la derniere ligne. Le
    cas verifie que la derniere ligne de contenu est toujours lisible.
    """
    octets = composer_pdf("Titre", [
        Titre("Section", 1),
        *[Paragraphe(f"Ligne de contenu numéro {i}.") for i in range(60)],
        Paragraphe("DERNIÈRE LIGNE DU DOCUMENT."),
    ])
    texte = _texte(octets)

    assert "DERNIÈRE LIGNE DU DOCUMENT." in texte
    assert "Ligne de contenu numéro 0." in texte
    assert "Ligne de contenu numéro 59." in texte


def test_le_flux_n_est_pas_comprime_et_se_lit_en_clair():
    """L'EMPREINTE NE DOIT DEPENDRE QUE DU CODE DE CE DEPOT.

    Le flux etait comprime par `zlib`, sous un commentaire affirmant que
    « la compression est deterministe sur toute plateforme ». C'etait faux: la
    sortie de `deflate` n'est pas normalisee — `zlib-ng` et les forks
    vectorises rendent d'autres octets — et Python se lie a la bibliotheque de
    la plateforme.

    Pour un document ADRESSE PAR SON CONTENU, c'est une dependance de trop:
    deux instances d'API derriere un repartiteur auraient pu ecrire deux
    objets pour un seul et meme calcul.

    LE GAIN SUPPLEMENTAIRE EST L'AUDITABILITE: le contenu se lit avec un
    editeur de texte, sans rien decompresser.
    """
    octets = rendre_note_pdf(PROJET, CALCUL, notice=NOTICE, mention=MENTION)

    assert b"/Filter" not in octets, "un filtre de flux est revenu"
    assert b"FlateDecode" not in octets
    # LE TEXTE EST LA, EN CLAIR, DANS LES OCTETS DU FICHIER.
    assert b"Note de calcul" in octets
    assert b"NON SIGNABLE" in octets
    # ET LE FICHIER RESTE VALIDE POUR UN LECTEUR TIERS.
    assert _pages(octets) >= 1
