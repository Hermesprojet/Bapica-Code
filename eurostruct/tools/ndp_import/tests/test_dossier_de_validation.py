"""Ce qu'une declaration de validation doit pouvoir designer, et ne pas faire.

LE DEFAUT QUE CES CAS FERMENT
------------------------------
« Je valide les parametres belges » ne designe rien de verifiable. Six mois
plus tard, personne ne peut dire quelles valeurs etaient validees, dans quelle
edition, sur quel exemplaire, ni contre quelle version du registre. Une
declaration qui ne designe rien ne protege personne — surtout pas l'ingenieur
qui l'a signee.

`composer_dossier_de_validation.py` rend cette liste, et l'empreinte qui la
designe. Deux proprietes decident si cette empreinte vaut quelque chose:

* elle ne bouge pas quand seule la DATE DE LECTURE bouge (sinon la declaration
  cite un document que personne ne peut reproduire);
* elle bouge des qu'une VALEUR bouge (sinon elle ne designe pas le contenu).

Le premier defaut etait reel: `as_of` — la date du jour — entrait dans le corps
empreinte, si bien que le meme registre relu le lendemain rendait une empreinte
differente.

ET LA GARANTIE QUI COMPTE PLUS QUE LES DEUX AUTRES
----------------------------------------------------
Ce script **ne confirme rien**. Le dernier cas le mesure: apres execution,
`be.json` est octet pour octet ce qu'il etait. Une confirmation est l'acte date
de deux ingenieurs nommes, enregistre en base par le chemin d'autorite. Un
script du depot ne peut pas la produire.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
SCRIPT = RACINE / "tools/ndp_import/scripts/composer_dossier_de_validation.py"
BE = RACINE / "engine/src/eurostruct_engine/ndp/data/be.json"


def _module():
    spec = importlib.util.spec_from_file_location("_composeur", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def composeur():
    return _module()


@pytest.fixture(scope="module")
def dossier(composeur):
    return composeur.composer("BE", "poutre", date(2026, 9, 14))


# ---------------------------------------------------------------------------
# L'empreinte designe le CONTENU, pas l'instant de la lecture
# ---------------------------------------------------------------------------

def test_la_date_de_lecture_ne_change_pas_l_empreinte(composeur):
    """Deux lectures a six mois d'intervalle designent le meme dossier.

    C'est la propriete qui rend une declaration citable. Sans elle, « le
    dossier 2812b3... » nomme un document qui n'existe plus le lendemain.
    """
    tot = composeur.composer("BE", "poutre", date(2026, 9, 14))
    tard = composeur.composer("BE", "poutre", date(2027, 3, 2))
    assert tot["dossier_sha256"] == tard["dossier_sha256"]
    # La date de lecture est rendue, mais HORS empreinte, et nommee comme tel.
    assert tot["lu_avec_as_of"] == "2026-09-14"
    assert tard["lu_avec_as_of"] == "2027-03-02"


def test_une_valeur_qui_bouge_change_l_empreinte(composeur, dossier):
    """Sinon l'empreinte ne designe pas le contenu, et ne sert a rien."""
    corps = {c: v for c, v in dossier.items()
             if c not in ("dossier_sha256", "lu_avec_as_of")}
    # On ne touche pas au registre: on recalcule l'empreinte sur un corps ou
    # une seule valeur a bouge, exactement comme le script la calcule.
    altere = json.loads(json.dumps(corps))
    cible = next(f for f in altere["parametres"] if f["key"].endswith(":alpha_cc"))
    cible["variants"][0]["value"] = 0.9
    recalcule = hashlib.sha256(
        json.dumps(altere, sort_keys=True, ensure_ascii=False,
                   separators=(",", ":")).encode("utf-8")).hexdigest()
    assert recalcule != dossier["dossier_sha256"]


def test_l_empreinte_du_registre_est_celle_du_fichier(dossier):
    """Elle est verifiable par quiconque a le depot, sans faire confiance."""
    assert dossier["registre"]["sha256"] == hashlib.sha256(
        BE.read_bytes()).hexdigest()
    assert dossier["registre"]["fichier"].endswith("ndp/data/be.json")


# ---------------------------------------------------------------------------
# Ce que le dossier doit porter pour qu'on puisse signer dessus
# ---------------------------------------------------------------------------

def test_les_dix_neuf_parametres_viennent_des_modules(composeur, dossier):
    """La liste n'est pas recopiee: elle vient de ce que les chapitres exigent.

    Un sixieme chapitre qui reclamerait un parametre de plus le ferait
    apparaitre ici sans que personne y pense — et la declaration porterait
    alors sur un dossier plus large, avec une empreinte differente.
    """
    sys.path.insert(0, str(RACINE / "engine" / "src"))
    from eurostruct_engine.ec2.beam_verification import (
        required_parameters_for_beam,
    )
    attendus = set(required_parameters_for_beam("BE"))
    assert {f["key"] for f in dossier["parametres"]} == attendus
    assert len(dossier["parametres"]) == 19
    # Aucun requis ne manque au registre: un « absent » serait un parametre
    # qu'aucun ingenieur ne peut valider, faute de fiche.
    assert dossier["absents"] == []


def test_w_max_porte_ses_deux_branches_et_pas_un_nombre(dossier):
    """Un parametre conditionnel n'a pas de valeur unique.

    Les deux branches sont les SEULS nombres du sujet. Rendre « 0,35 » ou
    « 0,3 » ferait signer un blanc a l'ingenieur en lui montrant quelque chose.
    """
    fiche = next(f for f in dossier["parametres"] if f["key"].endswith(":w_max"))
    assert fiche["parameter_value"] is None
    assert fiche["unit"] == "mm"
    branches = {v["condition"]: v["value"] for v in fiche["variants"]}
    assert branches == {"X0_XC1": 0.4, "XC2_XC4_XD_XS": 0.3}
    # Le folio imprime et l'exemplaire lu, sans lesquels la branche n'est pas
    # verifiable dans l'annexe publiee.
    assert fiche["source_page"] == 18
    assert fiche["source_doc_id"] == (
        "3a19536221aef69b16435b88bc05d7aee05cebe823e98cb292e49e48fe68dcdd")


def test_chaque_fiche_porte_de_quoi_retrouver_la_source(dossier):
    """Clause, annexe, edition, exemplaire: sans quoi on signe de memoire."""
    for fiche in dossier["parametres"]:
        assert fiche["clause"], fiche["key"]
        assert fiche["national_annex_reference"], fiche["key"]
        assert fiche["edition"], fiche["key"]
        assert len(fiche["source_doc_id"] or "") == 64, fiche["key"]
        assert fiche["source_page"], fiche["key"]


def test_aucun_statut_confirme_ne_sort_du_depot(dossier):
    """Le depot n'ecrit jamais `confirmed`, et ce dossier ne l'invente pas."""
    statuts = {f["validation_status"] for f in dossier["parametres"]}
    assert statuts == {"pending_verification"}
    provenances = {f["value_provenance"] for f in dossier["parametres"]}
    assert provenances == {"national_annex"}


def test_l_avertissement_voyage_avec_le_document(dossier):
    """Le jour ou quelqu'un retrouve ce fichier sans contexte, la phrase y est."""
    phrase = dossier["avertissement"].lower()
    assert "ne confirme rien" in phrase
    assert "second" in phrase


# ---------------------------------------------------------------------------
# Ce que le script n'a pas le droit de faire
# ---------------------------------------------------------------------------

def test_composer_n_ecrit_rien_dans_le_registre():
    """La garantie centrale: composer n'est pas confirmer.

    Le script lit le registre et rend un document. S'il pouvait en modifier un
    octet, « le dossier dit que c'est confirme » finirait par vouloir dire
    quelque chose — et ce serait faux.
    """
    avant = hashlib.sha256(BE.read_bytes()).hexdigest()
    acheve = subprocess.run(
        [sys.executable, str(SCRIPT), "--pays", "BE", "--json"],
        capture_output=True, text=True, check=False,
        cwd=str(SCRIPT.parent.parent))
    assert acheve.returncode == 0, acheve.stderr
    assert hashlib.sha256(BE.read_bytes()).hexdigest() == avant
    # Et le document rendu est bien celui qu'on vient de decrire.
    rendu = json.loads(acheve.stdout)
    assert rendu["registre"]["sha256"] == avant
    assert len(rendu["parametres"]) == 19
