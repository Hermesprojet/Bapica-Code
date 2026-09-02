"""Proposer sans supprimer: les trois conditions, et la preuve qu'aucune
suppression n'est possible depuis ce chemin.

POURQUOI CES CAS EXISTENT
---------------------------
Le cout d'un objet conserve a tort est un peu d'espace disque. Le cout d'un
objet supprime a tort est un document qu'on ne peut plus produire devant un
tribunal, pendant les dix ans de la responsabilite decennale. Les deux erreurs
ne se valent pas, et chaque cas ci-dessous verifie que le produit choisit
toujours la premiere.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from eurostruct_api import orphelins
from eurostruct_api.orphelins import (
    DELAI_MINIMAL,
    GRACE_PAR_DEFAUT,
    Observation,
    proposer,
)

MAINTENANT = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)


def _obs(cle="o/p/aaa.pdf", *, vu_le, ecrit_le=None, empreinte="a" * 64,
         taille=1024, backend="minio"):
    return Observation(
        backend=backend, cle=cle, taille=taille, empreinte=empreinte,
        ecrit_le=ecrit_le or (MAINTENANT - timedelta(days=90)),
        vu_le=vu_le,
    )


# ===========================================================================
# 1 — LES TROIS CONDITIONS
# ===========================================================================
def test_deux_scans_separes_et_un_objet_ancien_donnent_un_candidat():
    m = proposer(
        [[_obs(vu_le=MAINTENANT - timedelta(days=3))],
         [_obs(vu_le=MAINTENANT - timedelta(hours=1))]],
        maintenant=MAINTENANT)

    assert len(m.candidats) == 1
    c = m.candidats[0]
    assert c.cle == "o/p/aaa.pdf"
    assert c.scans == 2
    assert c.premiere_detection.startswith("2026-08-29")
    assert c.derniere_detection.startswith("2026-09-01")
    assert "aucune ligne" in c.raison


def test_un_seul_scan_ne_propose_rien():
    """UN OBJET VU UNE FOIS PEUT AVOIR ETE DEPOSE UNE SECONDE AVANT LE SCAN."""
    m = proposer([[_obs(vu_le=MAINTENANT)]], maintenant=MAINTENANT)

    assert m.candidats == ()
    assert any("moins de deux scans" in str(e.get("reason"))
               for e in m.ecartes)


def test_un_objet_vu_seulement_au_second_scan_est_ecarte():
    m = proposer(
        [[], [_obs(vu_le=MAINTENANT)]],
        maintenant=MAINTENANT)

    assert m.candidats == ()
    assert any("une seule fois" in str(e["reason"]) for e in m.ecartes)


def test_des_scans_trop_rapproches_ne_proposent_rien():
    """VINGT-TROIS HEURES NE SUFFISENT PAS, ET C'EST DELIBERE.

    Le delai n'est pas une precaution vague: il doit couvrir une reprise, un
    deploiement ou une transaction interrompue.
    """
    m = proposer(
        [[_obs(vu_le=MAINTENANT - timedelta(hours=23))],
         [_obs(vu_le=MAINTENANT)]],
        maintenant=MAINTENANT)

    assert m.candidats == ()
    assert any("trop rapproches" in str(e["reason"]) for e in m.ecartes)


def test_un_objet_recent_reste_protege_par_l_age_de_grace():
    """UN OBJET ECRIT CE MOIS-CI N'EST PAS UN DECHET, quoi qu'en dise un scan."""
    m = proposer(
        [[_obs(vu_le=MAINTENANT - timedelta(days=3),
               ecrit_le=MAINTENANT - timedelta(days=5))],
         [_obs(vu_le=MAINTENANT,
               ecrit_le=MAINTENANT - timedelta(days=5))]],
        maintenant=MAINTENANT)

    assert m.candidats == ()
    assert any("age de grace" in str(e["reason"]) for e in m.ecartes)


def test_les_octets_changes_entre_deux_scans_ecartent_la_cle():
    """DEUX OBJETS DIFFERENTS SOUS LA MEME CLE NE SONT PAS UN ORPHELIN VU DEUX FOIS.

    Proposer celui-ci reviendrait a proposer la suppression du SECOND en
    croyant parler du premier.
    """
    m = proposer(
        [[_obs(vu_le=MAINTENANT - timedelta(days=3), empreinte="a" * 64)],
         [_obs(vu_le=MAINTENANT, empreinte="b" * 64)]],
        maintenant=MAINTENANT)

    assert m.candidats == ()
    assert any("octets ont change" in str(e["reason"]) for e in m.ecartes)


def test_une_cle_redevenue_referencee_est_nommee_dans_les_ecartes():
    """LA CANDIDATURE QUI TOMBE EST UNE INFORMATION, PAS UN SILENCE.

    Elle dit que la fenetre entre le depot et l'enregistrement etait en cause.
    """
    m = proposer(
        [[_obs(vu_le=MAINTENANT - timedelta(days=3))], []],
        maintenant=MAINTENANT)

    assert m.candidats == ()
    assert any("n'est plus orphelin" in str(e["reason"]) for e in m.ecartes)


# ===========================================================================
# 2 — LE MANIFESTE
# ===========================================================================
def test_le_manifeste_declare_le_mode_et_l_absence_de_suppression():
    m = proposer(
        [[_obs(vu_le=MAINTENANT - timedelta(days=3))],
         [_obs(vu_le=MAINTENANT)]],
        maintenant=MAINTENANT)
    d = json.loads(m.en_json())

    assert d["mode"] == "dry-run"
    assert d["no_deletion_performed"] is True
    assert d["policy"]["required_scans"] == 2
    assert d["policy"]["minimum_interval_hours"] == 24.0
    assert d["policy"]["grace_period_days"] == 30.0
    assert "Aucun objet n'a ete supprime" in d["notice"]
    # LE FORMAT EST VERSIONNE: un outil qui ne connait pas la version doit
    # refuser le manifeste, pas l'interpreter au mieux.
    assert d["format"] == "eurostruct/orphan-proposal"
    assert d["version"] == 1


def test_le_manifeste_a_une_empreinte_stable():
    """C'EST CE QUE L'OUTIL DE MAINTENANCE DEVRA EXIGER.

    Un manifeste transmis puis retouche — une cle ajoutee a la main — ne doit
    pas passer pour la proposition qui a ete relue.
    """
    scans = [[_obs(vu_le=MAINTENANT - timedelta(days=3))],
             [_obs(vu_le=MAINTENANT)]]
    a = proposer(scans, maintenant=MAINTENANT)
    b = proposer(scans, maintenant=MAINTENANT)

    assert a.en_json() == b.en_json()
    assert a.empreinte() == b.empreinte()
    assert len(a.empreinte()) == 64


def test_l_empreinte_change_si_un_candidat_change():
    a = proposer([[_obs(vu_le=MAINTENANT - timedelta(days=3))],
                  [_obs(vu_le=MAINTENANT)]], maintenant=MAINTENANT)
    b = proposer([[_obs(cle="o/p/bbb.pdf", vu_le=MAINTENANT - timedelta(days=3))],
                  [_obs(cle="o/p/bbb.pdf", vu_le=MAINTENANT)]],
                 maintenant=MAINTENANT)

    assert a.empreinte() != b.empreinte()


def test_les_candidats_sont_ordonnes():
    """UN ORDRE FIXE, sans quoi l'empreinte du manifeste ne veut rien dire."""
    scans = [
        [_obs(cle="o/p/ccc.pdf", vu_le=MAINTENANT - timedelta(days=3)),
         _obs(cle="o/p/aaa.pdf", vu_le=MAINTENANT - timedelta(days=3)),
         _obs(cle="o/p/bbb.pdf", vu_le=MAINTENANT - timedelta(days=3))],
        [_obs(cle="o/p/ccc.pdf", vu_le=MAINTENANT),
         _obs(cle="o/p/aaa.pdf", vu_le=MAINTENANT),
         _obs(cle="o/p/bbb.pdf", vu_le=MAINTENANT)],
    ]
    m = proposer(scans, maintenant=MAINTENANT)

    assert [c.cle for c in m.candidats] == [
        "o/p/aaa.pdf", "o/p/bbb.pdf", "o/p/ccc.pdf"]


# ===========================================================================
# 3 — CE MODULE NE SAIT PAS SUPPRIMER, ET C'EST VERIFIABLE
# ===========================================================================
def test_le_module_ne_contient_aucun_appel_de_suppression():
    """LA GARANTIE STRUCTURELLE, ET ELLE EST GROSSIERE EXPRES.

    Un controle sur le texte du module ne peut pas etre contourne par
    inadvertance: ajouter une suppression ici fait tomber ce cas.
    """
    import pathlib

    source = pathlib.Path(orphelins.__file__).read_text(encoding="utf-8")
    corps = "\n".join(
        ligne for ligne in source.splitlines()
        if not ligne.lstrip().startswith(("#", "*"))
    )
    for interdit in ("delete_object", "DeleteObject", "os.remove", "shutil.rm",
                     "unlink(", '"DELETE"', "method='DELETE'"):
        assert interdit not in corps, (
            f"« {interdit} » entre dans le module de proposition: il ne doit "
            "PAS savoir supprimer.")


def test_le_module_n_expose_aucune_fonction_d_execution():
    """L'API PUBLIQUE NE PROPOSE QU'UNE PROPOSITION."""
    assert set(orphelins.__all__) == {
        "DELAI_MINIMAL", "GRACE_PAR_DEFAUT",
        "Candidat", "Manifeste", "Observation", "proposer",
    }


def test_les_valeurs_par_defaut_sont_celles_de_la_politique():
    assert DELAI_MINIMAL == timedelta(hours=24)
    assert GRACE_PAR_DEFAUT == timedelta(days=30)
