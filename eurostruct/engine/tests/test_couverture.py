"""Trois états, trois gestes, et ils ne se déduisent pas l'un de l'autre.

CE QUE LE PRODUIT ANNONÇAIT
----------------------------
« 0 sur 29 », compté dans les fichiers du dépôt. Ce nombre ne bouge jamais —
le dépôt n'écrit jamais `confirmed`, et il n'a pas à l'écrire — donc il ne
décrit **aucune** instance. Il disait la même chose d'une base vierge et d'une
base où deux ingénieurs auraient signé les dix-neuf paramètres belges.

Les cas ci-dessous mesurent la separation des trois etats et, surtout, les
cas ou ils DIVERGENT: c'est la que le compte unique trompait.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from eurostruct_engine.ec2.beam_verification import required_parameters_for_beam
from eurostruct_engine.ndp import couverture_du_calcul, load_parameter_set
from eurostruct_engine.ndp.canonical import EvidenceItem
from eurostruct_engine.ndp.confirmation import (
    NormativeReviewPackage,
    NormativeRuleConfirmation,
    required_sources,
)
from eurostruct_engine.ndp.dossier import CitationDeRevue, composer_dossier

FICTIF = "FICTIF-"
AU = date(2026, 9, 14)
INSTANT = datetime(2026, 9, 14, 9, 0, tzinfo=UTC)
PAYS = "BE"


def _paquet(parametre) -> NormativeReviewPackage:
    compose = composer_dossier(
        parametre,
        statement=f"FICTIF — relu {parametre.clause}.",
        citations=(CitationDeRevue(
            document_digest=parametre.source_doc_id,
            quote="FICTIF — citation relevee.",
            page_printed=parametre.source_page or 1,
        ),),
    )
    return NormativeReviewPackage.of(
        country_code=parametre.country_code,
        standard_family=parametre.standard_family,
        part=parametre.part,
        rule_id=parametre.key,
        stack=compose.stack,
        normative_spec=compose.normative_spec,
        implementation=compose.implementation,
        evidence_items=tuple(
            EvidenceItem(
                document_digest=s.document_digest, document_role=s.role,
                reference=s.reference, edition=s.edition or parametre.edition,
                clause=s.clause, page_printed=parametre.source_page or 1,
                quote="FICTIF — citation relevee.", page_pdf=None,
            )
            for s in required_sources(compose.normative_spec)
        ),
    )


def _signatures(paquet, nom, qui=("alice", "bob")):
    return [
        NormativeRuleConfirmation.for_package(
            paquet,
            confirmation_id=f"{FICTIF}conf-{q}-{nom}",
            verifier_id=f"{FICTIF}{q}",
            verifier_name=f"FICTIF {q.title()}",
            verified_at=INSTANT,
            authorisations_at_signature=frozenset(
                {"can_validate_normative_reference"}),
            authorisation_scope_at_signature="BE/EN 1992/1-1",
            statement=f"FICTIF — {q} a relu la clause a la page citee.",
            idempotency_key=f"{FICTIF}idem-{q}-{nom}",
        )
        for q in qui
    ]


class FournisseurFictif:
    provider_identity = "FICTIF://couverture"
    is_fictional = True

    def __init__(self, confirmations=()) -> None:
        self._c = tuple(confirmations)

    def confirmations_for(self, rule_id: str):
        return tuple(c for c in self._c if c.rule_id == rule_id)

    def revocations_for(self, rule_id: str):
        return ()


@pytest.fixture(scope="module")
def jeu():
    return load_parameter_set(PAYS, strict=True, as_of=AU)


@pytest.fixture(scope="module")
def requis():
    return required_parameters_for_beam(PAYS)


# ===========================================================================
# 1. Sans base: « non interrogee », et surtout pas « zero »
# ===========================================================================
def test_sans_provider_la_base_n_est_pas_dite_vide(jeu, requis) -> None:
    """LES DEUX APPELLENT DES GESTES OPPOSES.

    « Aucune decision enregistree » envoie faire relire un parametre.
    « Aucune base branchee » envoie configurer l'instance. Les rendre par le
    meme zero envoie l'ingenieur au mauvais endroit.
    """
    c = couverture_du_calcul(jeu, requis, provider=None)

    assert c.base_interrogee is False
    assert c.provider_identity is None
    for p in c.parametres:
        assert p.decide_en_base is None, (
            f"{p.key}: sans base, « decide » doit etre inconnu, pas faux")
        assert p.utilisable is False
        assert "interrogee" in p.pourquoi

    # Le travail DOCUMENTAIRE, lui, est connu sans base: il est dans le depot.
    assert c.transcrits_nationalement == len(requis) == 19


# ===========================================================================
# 2. Avec base: les trois etats divergent, et c'est le point
# ===========================================================================
def test_une_couverture_partielle_se_lit_parametre_par_parametre(
    jeu, requis,
) -> None:
    """DIX-HUIT CONFIRMES SUR DIX-NEUF, ET LE CALCUL REFUSE.

    C'est exactement ce qu'un compte global cache. Le ratio dirait « 95 % »;
    l'ingenieur, lui, a besoin du nom du parametre qui manque.
    """
    ouverts = [c for c in requis if c != "EN 1992-1-1:w_max"]
    confirmations = []
    for cle in ouverts:
        p = jeu.find(cle)
        confirmations.extend(_signatures(_paquet(p), p.parameter_name))

    c = couverture_du_calcul(jeu, requis,
                             provider=FournisseurFictif(confirmations))

    assert c.base_interrogee is True
    assert c.provider_is_fictional is True
    assert c.utilisables == 18
    assert c.decides == 18
    assert c.prêt is False

    manquant = [p for p in c.parametres if not p.utilisable]
    assert [p.key for p in manquant] == ["EN 1992-1-1:w_max"]
    assert manquant[0].decide_en_base is False
    assert manquant[0].verificateurs == ()


def test_la_couverture_complete_ouvre_le_calcul(jeu, requis) -> None:
    confirmations = []
    for cle in requis:
        p = jeu.find(cle)
        confirmations.extend(_signatures(_paquet(p), p.parameter_name))

    c = couverture_du_calcul(jeu, requis,
                             provider=FournisseurFictif(confirmations))

    assert c.utilisables == len(requis) == 19
    assert c.prêt is True
    assert all(p.pourquoi == "" for p in c.parametres)


def test_les_verificateurs_viennent_de_la_base_et_sont_nommes(jeu,
                                                              requis) -> None:
    """QUI A SIGNE EST UN FAIT DE L'INSTANCE, pas du depot.

    Le depot ne porte aucun nom — `verified_by` y est nul partout. La
    couverture les rend parce que c'est la question suivante de l'ingenieur:
    « qui l'a validé ? ».
    """
    p = jeu.find("EN 1992-1-1:alpha_cc")
    fournisseur = FournisseurFictif(_signatures(_paquet(p), "alpha_cc"))

    c = couverture_du_calcul(jeu, ["EN 1992-1-1:alpha_cc"],
                             provider=fournisseur)

    (etat,) = c.parametres
    assert etat.decide_en_base is True
    assert etat.verificateurs == ("FICTIF Alice", "FICTIF Bob")
    assert etat.utilisable is True
    # Et le TRANSCRIT n'a pas bouge: le depot dit toujours la meme chose.
    assert etat.transcrit == "pending_verification"


def test_une_decision_qui_n_ouvre_pas_se_distingue_d_une_absence(
    jeu, requis,
) -> None:
    """LE TROISIEME CAS, ET LE PLUS TROMPEUR.

    Un parametre peut porter deux signatures authentiques ET rester
    inutilisable: le dossier signe ne correspond plus a ce que le registre
    detient. « Decide » et « utilisable » ne sont alors pas le meme fait, et
    le geste a faire n'est pas le meme non plus — il faut REFAIRE passer le
    parametre, pas le faire signer.
    """
    import dataclasses

    p = jeu.find("EN 1992-1-1:alpha_cc")
    # Deux ingenieurs signent un dossier compose sur une AUTRE valeur.
    faux = dataclasses.replace(p, variants=tuple(
        dataclasses.replace(v, value=0.5) for v in p.variants))
    fournisseur = FournisseurFictif(_signatures(_paquet(faux), "alpha_cc"))

    c = couverture_du_calcul(jeu, ["EN 1992-1-1:alpha_cc"],
                             provider=fournisseur)

    (etat,) = c.parametres
    assert etat.decide_en_base is True, "deux signatures existent bien en base"
    assert etat.verificateurs == ("FICTIF Alice", "FICTIF Bob")
    assert etat.utilisable is False, "et elles n'ouvrent rien"
    assert "variantes" in etat.pourquoi


def test_un_parametre_absent_du_registre_se_dit_absent(jeu) -> None:
    c = couverture_du_calcul(jeu, ["EN 1992-1-1:parametre_qui_n_existe_pas"])
    (etat,) = c.parametres
    assert etat.transcrit == "absent"
    assert etat.utilisable is False


def test_la_liste_des_requis_vient_des_modules(jeu) -> None:
    """Elle n'est recopiee nulle part: un module qui en ajoute un le montre."""
    c = couverture_du_calcul(jeu, required_parameters_for_beam(PAYS))
    assert c.requis == tuple(sorted(required_parameters_for_beam(PAYS)))
    assert "EN 1992-1-1:w_max" in c.requis
