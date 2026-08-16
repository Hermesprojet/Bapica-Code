"""Jalon 6.3a — modèle de domaine immuable de la confirmation normative.

Aucune base de données ici. Ces tests portent sur les objets et leur
comportement : immuabilité, invariants, décompte à quatre yeux, séparation
entre confirmation et révocation.

Deux propriétés valent d'être signalées, parce qu'elles sont faciles à croire
acquises et ne le sont pas :

* ``frozen=True`` gèle l'**attribut**, pas ce qu'il contient. Un champ déclaré
  ``tuple`` mais reçu en ``list`` resterait modifiable après construction.
* aucune confirmation ne porte de ``project_id``. Ce n'est pas un oubli à
  combler plus tard : le rattachement à un client est ce qui transformerait une
  lecture d'annexe en engagement professionnel sur une étude.
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timedelta, timezone

import pytest

from eurostruct_engine.ndp.canonical import Digest, EvidenceItem, digest_of
from eurostruct_engine.ndp.confirmation import (
    DOMAIN_OBJECTS,
    FICTIONAL_PREFIX,
    FORBIDDEN_FIELD_FRAGMENTS,
    ConfirmationDomainError,
    ConfirmationPolicy,
    ConfirmationProvider,
    ConfirmationStatus,
    InMemoryConfirmationProvider,
    NormativeContext,
    NormativeRuleConfirmation,
    NormativeRuleConfirmationRevocation,
    NormativeStack,
    NormativeStackComponent,
    assert_provider_is_usable_in_production,
    assess_confirmations,
    field_names,
    independent_regards,
)

BRUXELLES = timezone(timedelta(hours=1))
INSTANT = datetime(2026, 3, 4, 14, 30, tzinfo=BRUXELLES)

SPEC = digest_of({"regle": "be.ec2.nu", "quoi": "specification"})
IMPL = digest_of({"regle": "be.ec2.nu", "quoi": "implementation"})
PREUVE = digest_of({"regle": "be.ec2.nu", "quoi": "preuve"})


# ---------------------------------------------------------------------------
# Fabriques de fixtures — toutes explicitement fictives
# ---------------------------------------------------------------------------
def pile(*, edition_annexe: str = "2010") -> NormativeStack:
    return NormativeStack.of(
        country_code="BE",
        standard_family="EN 1992",
        part="1-1",
        components=(
            NormativeStackComponent("base", "EN 1992-1-1", "2004", 1, "a" * 64),
            NormativeStackComponent(
                "annexe", "NBN EN 1992-1-1 ANB", edition_annexe, 2, "b" * 64,
            ),
        ),
    )


def preuve_lue() -> EvidenceItem:
    return EvidenceItem(
        document_digest="b" * 64, document_role="annexe",
        reference="NBN EN 1992-1-1 ANB", edition="2010",
        clause="§6.2.2(6)", page_printed=15,
        quote="FICTIF — citation de test, sans valeur normative.",
    )


def confirmation(
    *, verifier: str = "alice", cid: str | None = None,
    cle: str | None = None, spec: Digest = SPEC, impl: Digest = IMPL,
    stack: NormativeStack | None = None, **remplacements,
) -> NormativeRuleConfirmation:
    """Une confirmation fictive. Le préfixe est porté par les identités."""
    vid = f"{FICTIONAL_PREFIX}{verifier}"
    base = {
        "confirmation_id": cid or f"{FICTIONAL_PREFIX}conf-{verifier}",
        "country_code": "BE",
        "standard_family": "EN 1992",
        "part": "1-1",
        "rule_id": "be.ec2.nu_strength_reduction",
        "normative_spec": spec,
        "implementation": impl,
        "evidence": PREUVE,
        "stack": stack if stack is not None else pile(),
        "verifier_id": vid,
        "verifier_name": f"FICTIF {verifier.title()}",
        "verified_at": INSTANT,
        "authorisations_at_signature": frozenset(
            {"can_validate_normative_reference"}
        ),
        "authorisation_scope_at_signature": "BE/EN 1992/1-1",
        "evidence_items": (preuve_lue(),),
        "statement": "FICTIF — j'ai lu l'annexe a la page indiquee.",
        "idempotency_key": cle or f"{FICTIONAL_PREFIX}idem-{verifier}",
    }
    base.update(remplacements)
    return NormativeRuleConfirmation(**base)


def revocation(cible: NormativeRuleConfirmation, **remplacements):
    base = {
        "revocation_id": f"{FICTIONAL_PREFIX}rev-{cible.verifier_id}",
        "confirmation_id": cible.confirmation_id,
        "revoked_by": f"{FICTIONAL_PREFIX}carole",
        "revoked_by_name": "FICTIF Carole",
        "revoked_at": INSTANT + timedelta(days=1),
        "authorisations_at_revocation": frozenset(
            {"can_validate_normative_reference"}
        ),
        "reason": "FICTIF — relecture ulterieure: page erronee.",
    }
    base.update(remplacements)
    return NormativeRuleConfirmationRevocation(**base)


def contexte(*, edition_annexe: str = "2010", strict: bool = False):
    return NormativeContext(
        stack=pile(edition_annexe=edition_annexe),
        as_of=date(2026, 3, 4),
        strict=strict,
    )


# ---------------------------------------------------------------------------
# 1. Immuabilité
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("objet", DOMAIN_OBJECTS, ids=lambda o: o.__name__)
def test_chaque_objet_de_domaine_est_gele(objet) -> None:
    """Exigence 1 — aucun champ ne se réaffecte après construction."""
    assert dataclasses.is_dataclass(objet)
    parametres = objet.__dataclass_params__
    assert parametres.frozen, f"{objet.__name__} n'est pas frozen"
    assert getattr(objet, "__slots__", None) is not None, (
        f"{objet.__name__} sans slots: un attribut arbitraire pourrait y etre "
        "ajoute, ce qu'un objet signe ne doit pas permettre"
    )


def test_reaffecter_un_champ_est_refuse() -> None:
    c = confirmation()
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.statement = "autre chose"
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.verifier_id = "quelqu_un_d_autre"


def test_le_contenu_des_collections_est_gele_aussi() -> None:
    """``frozen`` gèle l'attribut, pas ce qu'il contient.

    Un champ déclaré ``tuple`` mais reçu en ``list`` laisserait la confirmation
    modifiable après signature tout en se présentant comme immuable.
    """
    with pytest.raises(ConfirmationDomainError, match="tuple est requis"):
        confirmation(evidence_items=[preuve_lue()])
    with pytest.raises(ConfirmationDomainError, match="frozenset est requis"):
        confirmation(authorisations_at_signature={"can_validate_normative_reference"})

    c = confirmation()
    with pytest.raises(AttributeError):
        c.evidence_items.append(preuve_lue())


def test_l_empreinte_de_pile_ne_peut_pas_etre_fournie() -> None:
    """Elle est calculée depuis la structure, jamais reçue.

    Un appelant qui fournirait le digest pourrait en donner un qui ne
    correspond pas à ce qu'il prétend résumer.
    """
    with pytest.raises(TypeError):
        NormativeStack(
            schema_version="esc-stack/1", country_code="BE",
            standard_family="EN 1992", part="1-1", components=(),
            digest=SPEC,
        )
    p = pile()
    assert p.digest == digest_of({
        "kind": "normative_stack",
        "schema_version": "esc-stack/1",
        "country_code": "BE",
        "standard_family": "EN 1992",
        "part": "1-1",
        "components": [
            {"role": "base", "reference": "EN 1992-1-1", "edition": "2004",
             "application_order": 1, "document_digest": "a" * 64},
            {"role": "annexe", "reference": "NBN EN 1992-1-1 ANB",
             "edition": "2010", "application_order": 2,
             "document_digest": "b" * 64},
        ],
    })


# ---------------------------------------------------------------------------
# 2. Horodatage
# ---------------------------------------------------------------------------
def test_un_horodatage_sans_fuseau_est_refuse() -> None:
    """Exigence 2 — « 14:00 » n'est pas un instant.

    C'est une heure murale, dont le sens dépend d'où était la machine. Une
    confirmation est relue dix ans plus tard, depuis un autre pays, parfois
    après un changement d'heure.
    """
    with pytest.raises(ConfirmationDomainError, match="sans fuseau"):
        confirmation(verified_at=datetime(2026, 3, 4, 14, 30))

    c = confirmation()
    with pytest.raises(ConfirmationDomainError, match="sans fuseau"):
        revocation(c, revoked_at=datetime(2026, 3, 5, 9, 0))


def test_une_chaine_iso_ne_remplace_pas_un_instant() -> None:
    """Deux bibliothèques ne lisent pas une chaîne ISO de la même façon."""
    with pytest.raises(ConfirmationDomainError, match="datetime est requis"):
        confirmation(verified_at="2026-03-04T14:30:00+01:00")


def test_un_fuseau_explicite_est_accepte_et_conserve() -> None:
    c = confirmation()
    assert c.verified_at.tzinfo is not None
    assert c.verified_at.utcoffset() == timedelta(hours=1)


def test_le_contexte_refuse_un_datetime_la_ou_une_date_est_attendue() -> None:
    """La pile applicable se détermine au jour, pas à la seconde."""
    with pytest.raises(ConfirmationDomainError, match="date"):
        NormativeContext(stack=pile(), as_of=INSTANT)


# ---------------------------------------------------------------------------
# 3. Aucun rattachement à un projet client
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("objet", DOMAIN_OBJECTS, ids=lambda o: o.__name__)
def test_aucun_champ_ne_rattache_a_un_projet_ou_a_un_client(objet) -> None:
    """Exigence 3 — vérifié structurellement, sur chaque objet du module.

    Une liste écrite à la main deviendrait fausse le jour où un champ est
    ajouté. Ce test parcourt les objets déclarés et refuse tout nom contenant
    un fragment interdit.
    """
    for nom in field_names(objet):
        minuscule = nom.lower()
        for fragment in FORBIDDEN_FIELD_FRAGMENTS:
            assert fragment not in minuscule, (
                f"{objet.__name__}.{nom} contient '{fragment}': une "
                "confirmation normative ne se rattache a aucun client. La "
                "lecture d'une annexe est vraie pour tous les projets de la "
                "juridiction ou pour aucun."
            )


def test_l_affiliation_du_verificateur_est_de_l_audit_pas_un_droit() -> None:
    """Elle est conservée, et n'est lue par aucun contrôle.

    Le test le vérifie par la seule voie qui a du sens ici : la changer ne
    change strictement rien au résultat d'une évaluation.
    """
    sans = confirmation(verifier="alice")
    avec = dataclasses.replace(sans, verifier_affiliation="FICTIF Bureau SPRL")

    commun = dict(
        revocations=(), context=contexte(), normative_spec=SPEC,
        implementation=IMPL, policy=ConfirmationPolicy("test", 1),
    )
    a = assess_confirmations(confirmations=(sans,), **commun)
    b = assess_confirmations(confirmations=(avec,), **commun)
    assert a.status is b.status
    assert a.regards == b.regards


# ---------------------------------------------------------------------------
# 4-5. Confirmation et révocation
# ---------------------------------------------------------------------------
def test_la_confirmation_ne_porte_aucun_champ_de_revocation() -> None:
    """Exigence 4 — pas de ``is_revoked``, pas de ``revoked_at``.

    Un booléen mutable sur un enregistrement signé est exactement ce qu'une
    piste d'audit ne doit pas avoir : il rend indistinguables « jamais
    révoquée » et « révoquée puis remise ».
    """
    noms = field_names(NormativeRuleConfirmation)
    for interdit in ("is_revoked", "revoked", "revoked_at", "revoked_by",
                     "active", "status"):
        assert interdit not in noms, f"la confirmation porte '{interdit}'"


def test_la_revocation_est_un_objet_separe_avec_sa_propre_identite() -> None:
    c = confirmation()
    r = revocation(c)
    assert r.revocation_id != c.confirmation_id
    assert r.confirmation_id == c.confirmation_id
    assert type(r) is not type(c)


def test_revoquer_ne_modifie_pas_la_confirmation() -> None:
    """Exigence 5 — la confirmation révoquée reste lisible, à l'identique.

    Ce qui a été signé a été signé ; l'effacer effacerait la preuve de
    l'erreur.
    """
    c = confirmation()
    avant = dataclasses.astuple(c)

    r = revocation(c)
    provider = InMemoryConfirmationProvider(confirmations=(c,), revocations=(r,))

    assert dataclasses.astuple(c) == avant
    (rendue,) = provider.confirmations_for(c.rule_id)
    assert rendue is c, "le provider a copie ou reconstruit la confirmation"
    assert dataclasses.astuple(rendue) == avant


def test_une_revocation_sans_motif_est_refusee() -> None:
    """Sans raison, elle ne se distingue pas d'une fausse manœuvre."""
    c = confirmation()
    for vide in ("", "   ", "\n"):
        with pytest.raises(ConfirmationDomainError, match="motif"):
            revocation(c, reason=vide)


def test_la_revocation_n_exige_ni_pages_lues_ni_citation() -> None:
    """Révoquer n'est pas relire l'annexe."""
    noms = field_names(NormativeRuleConfirmationRevocation)
    for absent in ("evidence_items", "evidence", "page_printed", "quote"):
        assert absent not in noms


# ---------------------------------------------------------------------------
# 6. Idempotence technique ≠ décompte normatif
# ---------------------------------------------------------------------------
def test_l_idempotence_technique_est_distincte_de_l_identite_normative() -> None:
    """Exigence 6 — deux mécanismes, deux rôles.

    La clé d'idempotence empêche qu'un envoi rejoué crée deux lignes. Le
    décompte des regards se fait en ``verifier_id`` distincts. L'un ne dit rien
    de l'autre : deux envois distincts d'une même lecture ne font pas deux
    relecteurs.
    """
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1")
    b = confirmation(verifier="alice", cid="FICTIF-c2", cle="FICTIF-k2")

    # Clés d'idempotence différentes...
    assert a.idempotency_key != b.idempotency_key
    # ... et pourtant la MEME identite normative.
    assert a.normative_identity == b.normative_identity
    assert "FICTIF-k1" not in a.normative_identity

    # Donc un seul regard, malgre deux lignes acceptees par le stockage.
    assert independent_regards((a, b), ()) == {f"{FICTIONAL_PREFIX}alice"}


def test_une_cle_d_idempotence_repetee_est_refusee_par_le_stockage() -> None:
    """L'autre moitié: c'est bien un mécanisme de déduplication technique."""
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-meme")
    b = confirmation(verifier="bob", cid="FICTIF-c2", cle="FICTIF-meme")
    with pytest.raises(ConfirmationDomainError, match="idempotence"):
        InMemoryConfirmationProvider(confirmations=(a, b))


# ---------------------------------------------------------------------------
# 7-9. Politique quatre yeux
# ---------------------------------------------------------------------------
def test_la_politique_de_production_exige_deux_verificateurs_distincts() -> None:
    politique = ConfirmationPolicy.production()
    assert politique.minimum_independent_confirmations == 2
    assert politique.policy_version == "esc-policy/1"
    assert not politique.is_satisfied_by(1)
    assert politique.is_satisfied_by(2)


def test_la_politique_est_versionnee() -> None:
    """Le nombre exigé peut changer ; ce qui a été évalué sous quelle version
    ne doit pas devenir illisible."""
    assert ConfirmationPolicy("esc-policy/1", 2) != ConfirmationPolicy(
        "esc-policy/2", 2
    )
    with pytest.raises(ConfirmationDomainError, match="policy_version"):
        ConfirmationPolicy("", 2)
    with pytest.raises(ConfirmationDomainError, match=">= 1"):
        ConfirmationPolicy("esc-policy/1", 0)


def test_deux_lignes_du_meme_verificateur_font_un_seul_regard() -> None:
    """Exigence 7 — le décompte porte sur les ``verifier_id``, pas les lignes.

    Compter les lignes rendrait le quatre-yeux contournable par un simple
    double envoi.
    """
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1")
    b = confirmation(verifier="alice", cid="FICTIF-c2", cle="FICTIF-k2")

    verdict = assess_confirmations(
        confirmations=(a, b), revocations=(), context=contexte(),
        normative_spec=SPEC, implementation=IMPL,
        policy=ConfirmationPolicy.production(),
    )
    assert verdict.regards == {f"{FICTIONAL_PREFIX}alice"}
    assert verdict.status is ConfirmationStatus.INSUFFICIENT_INDEPENDENT_CONFIRMATIONS
    assert not verdict.is_confirmed
    assert "il en manque 1" in verdict.reason


def test_deux_verificateurs_distincts_font_deux_regards() -> None:
    """Exigence 8."""
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1")
    b = confirmation(verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2")

    verdict = assess_confirmations(
        confirmations=(a, b), revocations=(), context=contexte(),
        normative_spec=SPEC, implementation=IMPL,
        policy=ConfirmationPolicy.production(),
    )
    assert verdict.regards == {
        f"{FICTIONAL_PREFIX}alice", f"{FICTIONAL_PREFIX}bob",
    }
    assert verdict.status is ConfirmationStatus.VALID_FOR_CONTEXT
    assert verdict.is_confirmed


def test_l_etat_intermediaire_a_une_seule_confirmation_existe() -> None:
    """Une confirmation valide mais seule n'est ni « absente » ni « confirmée ».

    Confondre les deux ferait soit perdre le premier regard, soit rendre la
    règle utilisable avec un seul.
    """
    verdict = assess_confirmations(
        confirmations=(confirmation(verifier="alice"),), revocations=(),
        context=contexte(), normative_spec=SPEC, implementation=IMPL,
        policy=ConfirmationPolicy.production(),
    )
    assert verdict.status is ConfirmationStatus.INSUFFICIENT_INDEPENDENT_CONFIRMATIONS
    assert verdict.status is not ConfirmationStatus.ABSENT
    assert verdict.regards == {f"{FICTIONAL_PREFIX}alice"}
    assert f"{FICTIONAL_PREFIX}alice" in verdict.reason, (
        "savoir QUI a deja signe fait gagner du temps a qui cherche le second"
    )


def test_revoquer_une_des_deux_confirmations_ramene_a_un_regard() -> None:
    """Exigence 9 — et la révocation ne retire que la confirmation ciblée."""
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1")
    b = confirmation(verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2")
    politique = ConfirmationPolicy.production()

    avant = assess_confirmations(
        confirmations=(a, b), revocations=(), context=contexte(),
        normative_spec=SPEC, implementation=IMPL, policy=politique,
    )
    assert avant.is_confirmed

    apres = assess_confirmations(
        confirmations=(a, b), revocations=(revocation(b),), context=contexte(),
        normative_spec=SPEC, implementation=IMPL, policy=politique,
    )
    assert apres.regards == {f"{FICTIONAL_PREFIX}alice"}, (
        "la revocation de bob ne doit retirer que bob"
    )
    assert apres.status is ConfirmationStatus.INSUFFICIENT_INDEPENDENT_CONFIRMATIONS


def test_revoquer_toutes_les_confirmations_donne_l_etat_revoque() -> None:
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1")
    b = confirmation(verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2")
    verdict = assess_confirmations(
        confirmations=(a, b), revocations=(revocation(a), revocation(b)),
        context=contexte(), normative_spec=SPEC, implementation=IMPL,
        policy=ConfirmationPolicy.production(),
    )
    assert verdict.status is ConfirmationStatus.REVOKED
    assert verdict.status is not ConfirmationStatus.ABSENT


# ---------------------------------------------------------------------------
# 10. Piles incompatibles
# ---------------------------------------------------------------------------
def test_une_confirmation_faite_sur_une_autre_pile_ne_vaut_pas_ici() -> None:
    """Exigence 10 — et elle reste valide pour la pile qu'elle atteste.

    La nouveauté d'un document ne périme rien : la confirmation de l'édition
    2010 vaut pleinement pour un projet régi par 2010.
    """
    c = confirmation(stack=pile(edition_annexe="2010"))
    verdict = assess_confirmations(
        confirmations=(c,), revocations=(),
        context=contexte(edition_annexe="2018"),
        normative_spec=SPEC, implementation=IMPL,
        policy=ConfirmationPolicy("test", 1),
    )
    assert verdict.status is ConfirmationStatus.STACK_MISMATCH
    assert "restent valides" in verdict.reason
    # Le meme objet, evalue contre SA pile, reste confirme.
    assert assess_confirmations(
        confirmations=(c,), revocations=(),
        context=contexte(edition_annexe="2010"),
        normative_spec=SPEC, implementation=IMPL,
        policy=ConfirmationPolicy("test", 1),
    ).is_confirmed


def test_l_ecart_de_pile_est_annonce_avant_l_ecart_d_empreinte() -> None:
    """L'ordre des vérifications commande l'action de celui qui lit.

    Une confirmation faite sur une autre édition n'a aucune raison de porter
    les mêmes empreintes. Annoncer ``SPEC_MISMATCH`` enverrait chercher un
    défaut de transcription là où il n'y a qu'un écart d'édition.
    """
    c = confirmation(stack=pile(edition_annexe="2010"), spec=SPEC)
    verdict = assess_confirmations(
        confirmations=(c,), revocations=(),
        context=contexte(edition_annexe="2018"),
        normative_spec=digest_of({"regle": "autre"}), implementation=IMPL,
        policy=ConfirmationPolicy("test", 1),
    )
    assert verdict.status is ConfirmationStatus.STACK_MISMATCH


def test_l_ordre_des_composants_change_la_pile() -> None:
    """Un corrigendum appliqué après l'annexe ne donne pas le même texte."""
    with pytest.raises(ConfirmationDomainError, match="ordre d'application"):
        NormativeStack.of(
            country_code="BE", standard_family="EN 1992", part="1-1",
            components=(
                NormativeStackComponent("annexe", "ANB", "2010", 2, "b" * 64),
                NormativeStackComponent("base", "EN 1992-1-1", "2004", 1, "a" * 64),
            ),
        )
    with pytest.raises(ConfirmationDomainError, match="meme application_order"):
        NormativeStack.of(
            country_code="BE", standard_family="EN 1992", part="1-1",
            components=(
                NormativeStackComponent("base", "EN 1992-1-1", "2004", 1, "a" * 64),
                NormativeStackComponent("annexe", "ANB", "2010", 1, "b" * 64),
            ),
        )


def test_les_deux_mesempreintes_restent_distinguees() -> None:
    """Spec et implémentation n'envoient pas au même endroit."""
    commun = dict(
        revocations=(), context=contexte(),
        policy=ConfirmationPolicy("test", 1),
    )
    c = confirmation()

    spec = assess_confirmations(
        confirmations=(c,), normative_spec=digest_of({"autre": 1}),
        implementation=IMPL, **commun,
    )
    assert spec.status is ConfirmationStatus.SPEC_MISMATCH
    assert "rouvrir l'annexe" in spec.reason

    impl = assess_confirmations(
        confirmations=(c,), normative_spec=SPEC,
        implementation=digest_of({"autre": 1}), **commun,
    )
    assert impl.status is ConfirmationStatus.IMPLEMENTATION_MISMATCH
    assert "CODE" in impl.reason


def test_une_regle_sans_confirmation_est_absente() -> None:
    verdict = assess_confirmations(
        confirmations=(), revocations=(), context=contexte(),
        normative_spec=SPEC, implementation=IMPL,
        policy=ConfirmationPolicy.production(),
    )
    assert verdict.status is ConfirmationStatus.ABSENT
    assert verdict.regards == frozenset()


# ---------------------------------------------------------------------------
# 11-12. Provider mémoire
# ---------------------------------------------------------------------------
def test_le_provider_memoire_est_explicitement_fictif() -> None:
    """Exigence 11 — visible à l'œil nu dans un journal."""
    p = InMemoryConfirmationProvider()
    assert p.is_fictional is True
    assert "FICTIF" in p.provider_identity
    assert isinstance(p, ConfirmationProvider)


def test_le_provider_fictif_est_refuse_hors_des_tests() -> None:
    """Le crochet existe AVANT la machinerie de sélection.

    Une garantie ajoutée après le chemin qu'elle protège est une garantie que
    ce chemin a déjà pu contourner.
    """
    with pytest.raises(ConfirmationDomainError, match="fictif"):
        assert_provider_is_usable_in_production(InMemoryConfirmationProvider())


def test_le_provider_memoire_refuse_une_confirmation_non_fictive() -> None:
    """Exigence 12 — il ne PEUT PAS contenir une confirmation belge réelle.

    Pas « il n'en contient pas » : il la refuse à la construction. C'est ce qui
    empêche qu'un copier-coller malheureux rende une règle réelle confirmée.
    """
    reelle = dataclasses.replace(confirmation(), verifier_id="u-4711-reel")
    with pytest.raises(ConfirmationDomainError, match="FICTIF"):
        InMemoryConfirmationProvider(confirmations=(reelle,))

    c = confirmation()
    with pytest.raises(ConfirmationDomainError, match="FICTIF"):
        InMemoryConfirmationProvider(
            confirmations=(c,),
            revocations=(revocation(c, revoked_by="u-4711-reel"),),
        )


def test_aucune_confirmation_reelle_n_est_creee_par_ces_tests() -> None:
    """Exigence 12, l'autre moitié: le jeu de fixtures lui-même est fictif."""
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1")
    b = confirmation(verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2")
    p = InMemoryConfirmationProvider(confirmations=(a, b))

    for c in p.confirmations_for(a.rule_id):
        assert c.verifier_id.startswith(FICTIONAL_PREFIX)
        assert c.confirmation_id.startswith(FICTIONAL_PREFIX)
        assert "FICTIF" in c.verifier_name
        assert "FICTIF" in c.statement
        for item in c.evidence_items:
            assert "FICTIF" in item.quote


def test_le_provider_memoire_est_immuable() -> None:
    """Compléter un jeu de fixtures en place créerait une dépendance d'ordre
    entre tests — la panne la plus pénible à diagnostiquer."""
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1")
    b = confirmation(verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2")

    vide = InMemoryConfirmationProvider()
    un = vide.with_confirmations(a)
    deux = un.with_confirmations(b)

    assert vide.confirmations == ()
    assert un.confirmations == (a,)
    assert deux.confirmations == (a, b)
    assert un is not deux

    with pytest.raises(dataclasses.FrozenInstanceError):
        vide.confirmations = (a,)


def test_le_provider_rend_confirmations_et_revocations_de_la_regle() -> None:
    """L'API demandée: les deux, pour une règle donnée.

    Les révocations sont demandées AVEC les confirmations et non déduites d'un
    champ porté par elles — il n'existe pas de ``is_revoked`` à lire.
    """
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1")
    autre = confirmation(
        verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2",
        rule_id="be.ec2.s_t_max",
    )
    p = InMemoryConfirmationProvider(
        confirmations=(a, autre), revocations=(revocation(a),),
    )

    assert p.confirmations_for("be.ec2.nu_strength_reduction") == (a,)
    assert p.confirmations_for("be.ec2.s_t_max") == (autre,)
    assert p.confirmations_for("be.ec2.inconnue") == ()

    (r,) = p.revocations_for("be.ec2.nu_strength_reduction")
    assert r.confirmation_id == a.confirmation_id
    assert p.revocations_for("be.ec2.s_t_max") == ()


def test_plusieurs_confirmations_et_revocations_sans_postgresql() -> None:
    """Le provider mémoire sert exactement à cela."""
    cs = tuple(
        confirmation(verifier=n, cid=f"FICTIF-c{i}", cle=f"FICTIF-k{i}")
        for i, n in enumerate(("alice", "bob", "chloe", "david"))
    )
    p = InMemoryConfirmationProvider(confirmations=cs).with_revocations(
        revocation(cs[3], revocation_id="FICTIF-rev-d"),
    )
    verdict = assess_confirmations(
        confirmations=p.confirmations_for(cs[0].rule_id),
        revocations=p.revocations_for(cs[0].rule_id),
        context=contexte(), normative_spec=SPEC, implementation=IMPL,
        policy=ConfirmationPolicy.production(),
    )
    assert len(verdict.regards) == 3
    assert verdict.is_confirmed


# ---------------------------------------------------------------------------
# Ce que 6.3a ne fait PAS
# ---------------------------------------------------------------------------
def test_le_domaine_ne_depend_d_aucune_base_ni_du_registre_des_regles() -> None:
    """6.3a est un modèle de domaine: ni SQL, ni mode strict, ni readiness.

    Vérifié sur les imports du module plutôt qu'affirmé en commentaire.
    """
    import ast
    import inspect

    from eurostruct_engine.ndp import confirmation as module

    arbre = ast.parse(inspect.getsource(module))
    importes: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            importes |= {a.name for a in noeud.names}
        elif isinstance(noeud, ast.ImportFrom):
            importes.add(noeud.module or "")

    for interdit in ("psycopg", "psycopg2", "sqlalchemy", "asyncpg", "sqlite3"):
        assert not any(interdit in i for i in importes), (
            f"6.3a ne doit dependre d'aucune base: '{interdit}' importe"
        )
    assert not any(i.endswith("rules") or i.endswith("rules_be_ec2")
                   for i in importes), (
        "le modele de domaine ne doit pas dependre du registre des regles: "
        "les empreintes attendues lui sont PASSEES"
    )


def test_aucune_evaluation_de_regle_n_est_encore_branchee() -> None:
    """Le mode strict n'est pas branché — c'est un jalon ultérieur.

    Si `rules.py` importait déjà ce module, la readiness et le mode strict
    auraient commencé sans être demandés.
    """
    import inspect

    from eurostruct_engine.ndp import rules

    assert "confirmation" not in inspect.getsource(rules), (
        "rules.py fait deja reference aux confirmations: 6.3a devait rester "
        "un modele de domaine non branche"
    )
