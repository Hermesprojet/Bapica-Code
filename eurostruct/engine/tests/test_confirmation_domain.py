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

from eurostruct_engine.ndp.canonical import (
    CANONICALIZATION_VERSION,
    Digest,
    EvidenceItem,
    digest_of,
    evidence_digest,
)
from eurostruct_engine.ndp.confirmation import (
    DOMAIN_OBJECTS,
    FICTIONAL_PREFIX,
    FORBIDDEN_FIELD_FRAGMENTS,
    ConfirmationDomainError,
    ConfirmationPolicy,
    ConfirmationProvider,
    ConfirmationStatus,
    ConfirmationSubjectKey,
    ExclusionCause,
    InMemoryConfirmationProvider,
    NormativeContext,
    NormativeReviewPackage,
    NormativeRuleConfirmation,
    NormativeRuleConfirmationRevocation,
    NormativeStack,
    NormativeStackComponent,
    RequiredSource,
    ReviewerAttestationKey,
    assert_provider_is_usable_in_production,
    assess_confirmations,
    field_names,
    independent_regards,
    required_sources,
)

BRUXELLES = timezone(timedelta(hours=1))
INSTANT = datetime(2026, 3, 4, 14, 30, tzinfo=BRUXELLES)

#: Les documents de la spécification fictive. ``DOC_BASE`` porte DEUX sources —
#: le corps et son corrigendum — comme le PDF belge réel.
DOC_BASE = "a" * 64
DOC_ANB = "b" * 64
DOC_ETRANGER = "e" * 64


def payload_de_spec(rule_id: str = "be.ec2.nu_strength_reduction", *,
                    pdf_partage: bool = False,
                    labels_ambigus: bool = False) -> dict:
    """Un payload de spécification **de la même forme que le vrai**.

    Construit à la main plutôt qu'emprunté au registre des règles : le domaine
    ne doit pas en dépendre, et un test le vérifie. La forme, elle, est celle
    que produit ``normative_spec_digest`` — sans quoi la lecture des sources
    déclarées ne prouverait rien.

    ``pdf_partage`` ajoute un corrigendum **dans le même fichier** que le corps,
    reproduisant le cas belge où le corrigendum est relié à la norme de base.
    """
    sources = [
        {"reference": "FICTIF EN 1992-1-1", "layer": "base",
         "clause": "§9.2.2", "expression_label": "(9.5N)",
         "effect": "FICTIF — texte d'origine", "document_digest": DOC_BASE},
    ]
    if pdf_partage:
        sources.append({
            "reference": "FICTIF EN 1992-1-1/AC:2008", "layer": "corrigendum",
            "clause": "§9.2.2", "expression_label": "(9.5N)",
            "effect": "FICTIF — non modifiee",
            "document_digest": DOC_BASE,          # LE MEME FICHIER
        })
    if labels_ambigus:
        # Deux sources que la cle ne distingue pas et qui visent deux
        # expressions differentes: le paquet doit refuser.
        sources.append({
            "reference": "FICTIF EN 1992-1-1", "layer": "base",
            "clause": "§9.2.2", "expression_label": "(9.6N)",
            "effect": "FICTIF — autre expression", "document_digest": DOC_BASE,
        })
    return {
        "kind": "normative_spec",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "rule_id": rule_id,
        "expression_sources": sources,
        "normative_authority": {
            "country_code": "BE", "reference": "FICTIF NBN EN 1992-1-1 ANB",
            "edition": "2010", "clause": "§9.2.2(5)",
            "effect": "FICTIF — substitution nationale",
            "document_digest": DOC_ANB,
        },
    }


SPEC = digest_of(payload_de_spec())
SPEC_PDF_PARTAGE = digest_of(payload_de_spec(pdf_partage=True))
IMPL = digest_of({"regle": "be.ec2.nu", "quoi": "implementation"})


# ---------------------------------------------------------------------------
# Fabriques de fixtures — toutes explicitement fictives
# ---------------------------------------------------------------------------
def pile(*, edition_annexe: str = "2010") -> NormativeStack:
    return NormativeStack.of(
        country_code="BE",
        standard_family="EN 1992",
        part="1-1",
        components=(
            NormativeStackComponent("base", "EN 1992-1-1", "2004", 1, DOC_BASE),
            NormativeStackComponent(
                "annexe", "NBN EN 1992-1-1 ANB", edition_annexe, 2, DOC_ANB,
            ),
        ),
    )


def preuve_pour(src: RequiredSource, *, page: int = 15,
                citation: str | None = None, **ecarts) -> EvidenceItem:
    """Une preuve qui correspond **exactement** à *src*, sauf écarts demandés.

    Les écarts servent les tests négatifs : mauvaise clause, mauvais rôle,
    mauvaise édition. Page et citation, elles, ne participent pas à la
    correspondance — elles sont le contenu humain du dossier.
    """
    champs = {
        "document_digest": src.document_digest,
        "document_role": src.role,
        "reference": src.reference,
        "edition": src.edition or "2010",
        "clause": src.clause,
        "page_printed": page,
        "quote": citation or "FICTIF — citation de test, sans valeur normative.",
    }
    champs.update(ecarts)
    return EvidenceItem(**champs)


def dossier_pour(spec: Digest = SPEC, *, depart: int = 100,
                 sauf: int | None = None) -> tuple[EvidenceItem, ...]:
    """Un dossier couvrant **chaque source déclarée**, une preuve par source.

    ``sauf`` retire la n-ième source : c'est ainsi qu'un dossier incomplet se
    fabrique dans les tests, sans jamais deviner ce qui manque.
    """
    sources = required_sources(spec)
    return tuple(
        preuve_pour(src, page=depart + i)
        for i, src in enumerate(sources) if i != sauf
    )


def dossier_complet() -> tuple[EvidenceItem, ...]:
    return dossier_pour(SPEC)


def dossier_variante() -> tuple[EvidenceItem, ...]:
    """Mêmes sources, autres folios: un dossier valide mais **différent**."""
    return dossier_pour(SPEC, depart=900)


def paquet(*, edition_annexe: str = "2010", spec: Digest = SPEC,
           impl: Digest = IMPL, rule_id: str = "be.ec2.nu_strength_reduction",
           items: tuple[EvidenceItem, ...] | None = None,
           country_code: str = "BE", standard_family: str = "EN 1992",
           part: str = "1-1") -> NormativeReviewPackage:
    p = pile(edition_annexe=edition_annexe)
    if (country_code, standard_family, part) != ("BE", "EN 1992", "1-1"):
        p = dataclasses.replace(
            p, country_code=country_code, standard_family=standard_family,
            part=part,
        )
    return NormativeReviewPackage.of(
        country_code=country_code, standard_family=standard_family, part=part,
        rule_id=rule_id, stack=p, normative_spec=spec, implementation=impl,
        evidence_items=items if items is not None else dossier_pour(spec),
    )


def confirmation(
    *, verifier: str = "alice", cid: str | None = None,
    cle: str | None = None, package: NormativeReviewPackage | None = None,
    **remplacements,
) -> NormativeRuleConfirmation:
    """Une attestation fictive **sur un paquet de revue**.

    Passe par ``for_package``: c'est la voie qui garantit que le sujet signé
    est celui qui a été présenté.
    """
    vid = f"{FICTIONAL_PREFIX}{verifier}"
    base = {
        "confirmation_id": cid or f"{FICTIONAL_PREFIX}conf-{verifier}",
        "verifier_id": vid,
        "verifier_name": f"FICTIF {verifier.title()}",
        "verified_at": INSTANT,
        "authorisations_at_signature": frozenset(
            {"can_validate_normative_reference"}
        ),
        "authorisation_scope_at_signature": "BE/EN 1992/1-1",
        "statement": "FICTIF — j'ai lu l'annexe a la page indiquee.",
        "idempotency_key": cle or f"{FICTIONAL_PREFIX}idem-{verifier}",
    }
    base.update(remplacements)
    return NormativeRuleConfirmation.for_package(
        package if package is not None else paquet(), **base,
    )


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


def evalue(confirmations=(), revocations=(), *, attendu=None, politique=None):
    """Raccourci: évaluer contre un paquet attendu."""
    return assess_confirmations(
        expected=attendu if attendu is not None else paquet(),
        confirmations=tuple(confirmations),
        revocations=tuple(revocations),
        policy=politique or ConfirmationPolicy.production(),
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
        NormativeReviewPackage.of(
            country_code="BE", standard_family="EN 1992", part="1-1",
            rule_id="be.ec2.nu_strength_reduction", stack=pile(),
            normative_spec=SPEC, implementation=IMPL,
            evidence_items=list(dossier_complet()),
        )
    with pytest.raises(ConfirmationDomainError, match="frozenset est requis"):
        confirmation(authorisations_at_signature={"can_validate_normative_reference"})

    c = confirmation()
    with pytest.raises(AttributeError):
        c.evidence_items.append(preuve())


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

    a = evalue((sans,), politique=ConfirmationPolicy("test", 1))
    b = evalue((avec,), politique=ConfirmationPolicy("test", 1))
    assert a.status is b.status
    assert a.regards == b.regards
    assert sans.confirmation_subject_key == avec.confirmation_subject_key


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
    # ... et pourtant la MEME clé d'attestation, donc le même regard.
    assert a.reviewer_attestation_key == b.reviewer_attestation_key
    assert a.confirmation_subject_key == b.confirmation_subject_key

    # La clé d'idempotence n'entre dans AUCUNE des deux clés normatives.
    assert "FICTIF-k1" not in dataclasses.astuple(a.reviewer_attestation_key)
    assert "FICTIF-k1" not in str(dataclasses.astuple(a.confirmation_subject_key))

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
        expected=paquet(), confirmations=(a, b),
        revocations=(), policy=ConfirmationPolicy.production(),
    )
    assert verdict.regards == {f"{FICTIONAL_PREFIX}alice"}
    assert verdict.status is ConfirmationStatus.PARTIALLY_CONFIRMED
    assert not verdict.is_confirmed
    assert "il en manque 1" in verdict.reason


def test_deux_verificateurs_distincts_font_deux_regards() -> None:
    """Exigence 8."""
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1")
    b = confirmation(verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2")

    verdict = assess_confirmations(
        expected=paquet(), confirmations=(a, b),
        revocations=(), policy=ConfirmationPolicy.production(),
    )
    assert verdict.regards == {
        f"{FICTIONAL_PREFIX}alice", f"{FICTIONAL_PREFIX}bob",
    }
    assert verdict.status is ConfirmationStatus.CONFIRMED
    assert verdict.is_confirmed


def test_l_etat_intermediaire_a_une_seule_confirmation_existe() -> None:
    """Une confirmation valide mais seule n'est ni « absente » ni « confirmée ».

    Confondre les deux ferait soit perdre le premier regard, soit rendre la
    règle utilisable avec un seul.
    """
    verdict = evalue((confirmation(verifier="alice"),))
    assert verdict.status is ConfirmationStatus.PARTIALLY_CONFIRMED
    assert verdict.status is not ConfirmationStatus.UNCONFIRMED
    assert verdict.regards == {f"{FICTIONAL_PREFIX}alice"}
    assert f"{FICTIONAL_PREFIX}alice" in verdict.reason, (
        "savoir QUI a deja signe fait gagner du temps a qui cherche le second"
    )


def test_revoquer_une_des_deux_confirmations_ramene_a_un_regard() -> None:
    """Exigence 9 — et la révocation ne retire que la confirmation ciblée."""
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1")
    b = confirmation(verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2")
    politique = ConfirmationPolicy.production()

    avant = evalue((a, b), politique=politique)
    assert avant.is_confirmed

    apres = evalue((a, b), (revocation(b),), politique=politique)
    assert apres.regards == {f"{FICTIONAL_PREFIX}alice"}, (
        "la revocation de bob ne doit retirer que bob"
    )
    assert apres.status is ConfirmationStatus.PARTIALLY_CONFIRMED


def test_revoquer_toutes_les_confirmations_donne_l_etat_revoque() -> None:
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1")
    b = confirmation(verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2")
    verdict = evalue((a, b), (revocation(a), revocation(b)))
    assert verdict.status is ConfirmationStatus.REVOKED
    assert verdict.status is not ConfirmationStatus.UNCONFIRMED
    assert {e.cause for e in verdict.excluded} == {ExclusionCause.REVOKED}


# ---------------------------------------------------------------------------
# 10. Piles incompatibles
# ---------------------------------------------------------------------------
def test_une_confirmation_faite_sur_une_autre_pile_ne_vaut_pas_ici() -> None:
    """Exigence 10 — et elle reste valide pour la pile qu'elle atteste.

    La nouveauté d'un document ne périme rien : la confirmation de l'édition
    2010 vaut pleinement pour un projet régi par 2010.
    """
    c = confirmation(package=paquet(edition_annexe="2010"))
    solo = ConfirmationPolicy("test", 1)

    verdict = evalue((c,), attendu=paquet(edition_annexe="2018"), politique=solo)
    assert verdict.status is ConfirmationStatus.UNCONFIRMED
    (exclue,) = verdict.excluded
    assert exclue.cause is ExclusionCause.STACK_MISMATCH
    assert exclue.confirmation_id == c.confirmation_id
    assert "reste valide pour les calculs qui demandent sa pile" in exclue.detail

    # Le meme objet, evalue contre SA pile, reste confirme.
    assert evalue((c,), attendu=paquet(edition_annexe="2010"),
                  politique=solo).is_confirmed


def test_l_ecart_de_pile_est_annonce_avant_l_ecart_d_empreinte() -> None:
    """L'ordre des vérifications commande l'action de celui qui lit.

    Une confirmation faite sur une autre édition n'a aucune raison de porter
    les mêmes empreintes. Annoncer ``SPEC_MISMATCH`` enverrait chercher un
    défaut de transcription là où il n'y a qu'un écart d'édition.
    """
    c = confirmation(package=paquet(edition_annexe="2010"))
    attendu = paquet(edition_annexe="2018",
                     spec=digest_of(payload_de_spec("be.ec2.nu_strength_reduction")))
    (exclue,) = evalue((c,), attendu=attendu,
                       politique=ConfirmationPolicy("test", 1)).excluded
    assert exclue.cause is ExclusionCause.STACK_MISMATCH


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
    solo = ConfirmationPolicy("test", 1)
    c = confirmation()

    autre = payload_de_spec()
    autre["expression_sources"][0]["effect"] = "FICTIF — texte modifie"
    (par_spec,) = evalue(
        (c,), attendu=paquet(spec=digest_of(autre)), politique=solo,
    ).excluded
    assert par_spec.cause is ExclusionCause.SPEC_MISMATCH
    assert "rouvrir l'annexe" in par_spec.detail

    (par_impl,) = evalue(
        (c,), attendu=paquet(impl=digest_of({"autre": 1})), politique=solo,
    ).excluded
    assert par_impl.cause is ExclusionCause.IMPLEMENTATION_MISMATCH
    assert "CODE" in par_impl.detail


def test_une_regle_sans_confirmation_est_absente() -> None:
    verdict = evalue()
    assert verdict.status is ConfirmationStatus.UNCONFIRMED
    assert verdict.regards == frozenset()
    assert verdict.excluded == ()
    # Le sujet attendu est connu MALGRE l'absence d'attestation.
    assert verdict.subject == paquet().subject_key


# ---------------------------------------------------------------------------
# 6.3a1 — identité exacte du sujet confirmé
#
# `normative_identity = (rule_id, spec_digest, verifier_id)` était incomplète
# ET mal nommée: elle ne portait ni la pile, ni l'implémentation, ni la preuve,
# tout en s'annonçant comme « l'identité normative ». Une clé incomplète dont
# le nom promet la complétude finit par être utilisée comme telle.
# ---------------------------------------------------------------------------
def test_la_cle_de_sujet_porte_les_huit_composantes() -> None:
    """Exigence 9, première moitié — la clé complète est complète."""
    attendu = (
        "country_code", "standard_family", "part", "rule_id", "stack_digest",
        "normative_spec_digest", "implementation_digest", "evidence_digest",
    )
    assert field_names(ConfirmationSubjectKey) == attendu
    assert ConfirmationSubjectKey.REQUIRED_COMPONENTS == attendu

    c = confirmation()
    k = c.confirmation_subject_key
    assert k.stack_digest == c.stack.digest.digest
    assert k.normative_spec_digest == c.normative_spec.digest
    assert k.implementation_digest == c.implementation.digest
    assert k.evidence_digest == c.evidence.digest


def test_aucune_propriete_ne_s_appelle_identite_normative() -> None:
    """Exigence 9, seconde moitié — le nom trompeur a disparu.

    Le supprimer plutôt que le renommer: un nom qui promet une identité
    normative complète et n'en porte qu'un fragment sera utilisé comme clé
    complète tôt ou tard.
    """
    for objet in DOMAIN_OBJECTS + (NormativeRuleConfirmation,):
        for nom in dir(objet):
            assert "normative_identity" not in nom, (
                f"{objet.__name__}.{nom} ressuscite une cle incomplete"
            )

    c = confirmation()
    assert not hasattr(c, "normative_identity")


def test_la_cle_d_attestation_est_le_sujet_plus_le_verificateur() -> None:
    assert field_names(ReviewerAttestationKey) == ("subject", "verifier_id")
    c = confirmation()
    assert c.reviewer_attestation_key.subject == c.confirmation_subject_key
    assert c.reviewer_attestation_key.verifier_id == c.verifier_id


def test_les_cles_sont_immuables_et_deterministes() -> None:
    """Exigence 10 — deux calculs donnent la même clé, et rien ne s'y réaffecte."""
    c = confirmation()
    a, b = c.confirmation_subject_key, c.confirmation_subject_key
    assert a == b and hash(a) == hash(b)
    assert a is not b, "la propriete reconstruit: l'egalite ne vient pas d'un cache"

    ra, rb = c.reviewer_attestation_key, c.reviewer_attestation_key
    assert ra == rb and hash(ra) == hash(rb)

    with pytest.raises(dataclasses.FrozenInstanceError):
        a.rule_id = "autre"
    with pytest.raises(dataclasses.FrozenInstanceError):
        ra.verifier_id = "autre"

    # Deterministe: reconstruire la confirmation a l'identique redonne la cle.
    assert confirmation().confirmation_subject_key == a


@pytest.mark.parametrize(
    ("champ", "valeur"),
    [
        ("country_code", "FR"),
        ("standard_family", "EN 1993"),
        ("part", "1-2"),
        ("rule_id", "be.ec2.s_t_max"),
    ],
    ids=["pays", "norme", "partie", "regle"],
)
def test_chaque_composante_identitaire_change_la_cle_de_sujet(champ, valeur) -> None:
    base = confirmation()
    remplacements = {champ: valeur}
    if champ == "country_code":
        # La pile porte aussi le pays: l'invariant de coherence l'exige.
        remplacements["stack"] = dataclasses.replace(base.stack, country_code="FR")
    autre = dataclasses.replace(base, **remplacements)
    assert autre.confirmation_subject_key != base.confirmation_subject_key


def test_chaque_empreinte_change_la_cle_de_sujet() -> None:
    """Pile, spécification, implémentation, preuve: les quatre comptent."""
    base = confirmation()
    autre_spec = payload_de_spec()
    autre_spec["expression_sources"][0]["effect"] = "FICTIF — autre"

    for paquet_modifie in (
        paquet(spec=digest_of(autre_spec)),
        paquet(impl=digest_of({"autre": True})),
        paquet(edition_annexe="2018"),
        # Le dossier de preuve: un folio different suffit.
        paquet(items=dossier_variante()),
    ):
        autre = confirmation(package=paquet_modifie)
        assert autre.confirmation_subject_key != base.confirmation_subject_key


# --- le dossier de preuve, et ce qui n'en fait pas partie ------------------
def test_deux_verificateurs_sur_le_meme_sujet_donnent_CONFIRMED() -> None:
    """Exigence 1 — le cas nominal du contrôle à quatre yeux."""
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1")
    b = confirmation(verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2")
    assert a.confirmation_subject_key == b.confirmation_subject_key
    assert a.reviewer_attestation_key != b.reviewer_attestation_key

    verdict = assess_confirmations(
        expected=paquet(), confirmations=(a, b),
        revocations=(), policy=ConfirmationPolicy.production(),
    )
    assert verdict.status is ConfirmationStatus.CONFIRMED
    assert verdict.is_confirmed


def test_une_declaration_personnelle_differente_reste_combinable() -> None:
    """Exigence 6 — deux personnes n'écrivent jamais la même phrase.

    Faire dépendre le sujet de leur formulation rendrait le double contrôle
    inatteignable en pratique.
    """
    a = confirmation(
        verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1",
        statement="FICTIF — lu page 15, la formule correspond.",
    )
    b = confirmation(
        verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2",
        statement="FICTIF — verifie sur l'annexe, RAS. Note perso: relire 9.6N.",
        verified_at=INSTANT + timedelta(days=2),
    )
    assert a.statement != b.statement
    assert a.verified_at != b.verified_at
    assert a.verifier_id != b.verifier_id
    # ... et pourtant le MEME sujet.
    assert a.confirmation_subject_key == b.confirmation_subject_key

    verdict = assess_confirmations(
        expected=paquet(), confirmations=(a, b),
        revocations=(), policy=ConfirmationPolicy.production(),
    )
    assert verdict.is_confirmed


def test_un_commentaire_personnel_ne_change_pas_l_empreinte_de_preuve() -> None:
    """La déclaration appartient à l'attestation, jamais au dossier."""
    base = confirmation()
    bavard = dataclasses.replace(
        base, statement="FICTIF — " + "commentaire tres long. " * 20,
    )
    assert bavard.evidence == base.evidence
    assert bavard.confirmation_subject_key == base.confirmation_subject_key
    # Et le champ n'entre dans aucune des deux cles.
    assert "commentaire" not in str(
        dataclasses.astuple(bavard.confirmation_subject_key)
    )


def test_deux_dossiers_de_preuve_differents_donnent_EVIDENCE_MISMATCH() -> None:
    """Exigence 5 — même règle, même pile, même code, preuves différentes.

    Deux relecteurs qui n'ont pas ouvert les mêmes pages n'ont pas exercé deux
    regards sur la même chose.
    """
    mauvais = paquet(items=dossier_variante())
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1",
                     package=mauvais)
    b = confirmation(verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2",
                     package=mauvais)

    # Meme regle, meme pile, meme code — et pourtant pas le dossier attendu.
    assert a.normative_spec == b.normative_spec
    assert a.implementation == b.implementation
    assert a.stack.digest == b.stack.digest
    assert a.confirmation_subject_key == b.confirmation_subject_key
    assert a.confirmation_subject_key != paquet().subject_key

    verdict = evalue((a, b))
    assert verdict.status is ConfirmationStatus.UNCONFIRMED, (
        "s'accorder a deux sur le MAUVAIS dossier ne confirme pas le paquet "
        "attendu — c'est tout l'objet de 6.3a2"
    )
    assert not verdict.is_confirmed
    assert {e.cause for e in verdict.excluded} == {ExclusionCause.EVIDENCE_MISMATCH}
    assert verdict.has_divergent_attestations


def test_les_attestations_aux_preuves_divergentes_restent_conservees() -> None:
    """Elles ne sont pas additionnées; elles ne sont pas perdues non plus."""
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1")
    b = confirmation(
        verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2",
        package=paquet(items=dossier_variante()),
    )
    p = InMemoryConfirmationProvider(confirmations=(a, b))
    rendues = p.confirmations_for(a.rule_id)
    assert len(rendues) == 2
    assert set(rendues) == {a, b}

    # Et l'evaluation la SIGNALE au lieu de l'ignorer.
    (exclue,) = evalue((a, b)).excluded
    assert exclue.confirmation_id == b.confirmation_id
    assert exclue.cause is ExclusionCause.EVIDENCE_MISMATCH


def test_un_dossier_partage_par_deux_regards_confirme_malgre_un_dossier_tiers(
) -> None:
    """Un groupe qui satisfait à lui seul la politique est un double contrôle.

    L'attestation isolée sur un autre dossier reste conservée; elle n'est
    simplement pas additionnée.
    """
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1")
    b = confirmation(verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2")
    seul = confirmation(
        verifier="chloe", cid="FICTIF-c3", cle="FICTIF-k3",
        package=paquet(items=dossier_variante()),
    )
    verdict = evalue((a, b, seul))
    assert verdict.status is ConfirmationStatus.CONFIRMED
    assert verdict.regards == {
        f"{FICTIONAL_PREFIX}alice", f"{FICTIONAL_PREFIX}bob",
    }
    # L'attestation tierce n'est PAS silencieusement ignoree.
    (exclue,) = verdict.excluded
    assert exclue.confirmation_id == seul.confirmation_id
    assert exclue.cause is ExclusionCause.EVIDENCE_MISMATCH
    assert verdict.has_divergent_attestations
    assert "divergente" in verdict.reason


def test_une_attestation_revoquee_sur_un_autre_dossier_reste_diagnostiquee() -> None:
    """Depuis 6.3a2, la révocation vient APRÈS le désaccord de sujet.

    En 6.3a1 elle passait avant, pour qu'une attestation retirée ne produise
    pas un ``EVIDENCE_MISMATCH`` **global**. Ce risque a disparu avec le paquet
    attendu : le statut ne dépend plus que des attestations exactes, et
    annoncer le désaccord de dossier dit désormais quelque chose de plus utile
    — pourquoi elle a probablement été retirée.
    """
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1")
    retiree = confirmation(
        verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2",
        package=paquet(items=dossier_variante()),
    )
    verdict = evalue((a, retiree), (revocation(retiree),))
    assert verdict.status is ConfirmationStatus.PARTIALLY_CONFIRMED
    assert verdict.regards == {f"{FICTIONAL_PREFIX}alice"}
    (exclue,) = verdict.excluded
    assert exclue.cause is ExclusionCause.EVIDENCE_MISMATCH


# --- non-combinabilité par pile et par implémentation ----------------------
def test_memes_regle_et_spec_mais_piles_differentes_ne_se_combinent_pas() -> None:
    """Exigence 3."""
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1",
                     package=paquet(edition_annexe="2010"))
    b = confirmation(verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2",
                     package=paquet(edition_annexe="2018"))
    assert a.normative_spec == b.normative_spec
    assert a.confirmation_subject_key != b.confirmation_subject_key

    # Contre la pile de a: seul le regard de a compte.
    verdict = evalue((a, b), attendu=paquet(edition_annexe="2010"))
    assert verdict.regards == {f"{FICTIONAL_PREFIX}alice"}
    assert not verdict.is_confirmed
    assert verdict.excluded[0].cause is ExclusionCause.STACK_MISMATCH

    # Et l'addition brute est refusee a la racine.
    with pytest.raises(ConfirmationDomainError, match="sujets distincts"):
        independent_regards((a, b), ())


def test_memes_pile_et_spec_mais_implementations_differentes_ne_se_combinent_pas(
) -> None:
    """Exigence 4."""
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1")
    b = confirmation(verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2",
                     package=paquet(impl=digest_of({"code": "modifie"})))
    assert a.stack.digest == b.stack.digest
    assert a.normative_spec == b.normative_spec
    assert a.confirmation_subject_key != b.confirmation_subject_key

    verdict = evalue((a, b))
    assert verdict.regards == {f"{FICTIONAL_PREFIX}alice"}
    assert not verdict.is_confirmed
    assert verdict.excluded[0].cause is ExclusionCause.IMPLEMENTATION_MISMATCH

    with pytest.raises(ConfirmationDomainError, match="sujets distincts"):
        independent_regards((a, b), ())


def test_l_ordre_des_controles_est_celui_qui_est_documente() -> None:
    """Sujet etranger, pile, specification, implementation, preuve, revocation.

    Chaque etape est verifiee en rendant fautives toutes celles qui suivent: si
    l'ordre changeait, la cause annoncee changerait aussi. Une attestation
    peut diverger de plusieurs facons a la fois, et c'est la cause la plus
    LARGE qui doit etre annoncee — celle qui dit quoi faire.
    """
    autre_spec_payload = payload_de_spec()
    autre_spec_payload["expression_sources"][0]["effect"] = "FICTIF — autre"
    autre_spec = digest_of(autre_spec_payload)
    autre_impl = digest_of({"code": "autre"})
    mauvais_dossier = dossier_variante()
    attendu = paquet()

    def cause(signee: NormativeReviewPackage, revoquee: bool = False):
        c = confirmation(package=signee)
        rev = (revocation(c),) if revoquee else ()
        (exclue,) = evalue((c,), rev, attendu=attendu,
                           politique=ConfirmationPolicy("test", 1)).excluded
        return exclue.cause

    # 1. autre regle + tout le reste fautif -> OTHER_SUBJECT.
    #    Ce n'est meme pas un desaccord: l'attestation parle d'autre chose.
    assert cause(paquet(
        rule_id="be.ec2.s_t_max",
        spec=digest_of(payload_de_spec("be.ec2.s_t_max")),
        impl=autre_impl, edition_annexe="2018", items=mauvais_dossier,
    )) is ExclusionCause.OTHER_SUBJECT

    # 2. bonne regle, autre pile + spec + impl + dossier fautifs -> STACK.
    assert cause(paquet(
        edition_annexe="2018", spec=autre_spec, impl=autre_impl,
        items=mauvais_dossier,
    )) is ExclusionCause.STACK_MISMATCH

    # 3. bonne pile, spec + impl + dossier fautifs -> SPEC.
    assert cause(paquet(
        spec=autre_spec, impl=autre_impl, items=mauvais_dossier,
    )) is ExclusionCause.SPEC_MISMATCH

    # 4. bonne spec, impl + dossier fautifs -> IMPLEMENTATION.
    assert cause(paquet(
        impl=autre_impl, items=mauvais_dossier,
    )) is ExclusionCause.IMPLEMENTATION_MISMATCH

    # 5. tout bon sauf le dossier -> EVIDENCE.
    assert cause(paquet(items=mauvais_dossier)) is ExclusionCause.EVIDENCE_MISMATCH

    # 6. tout bon, mais retiree -> REVOKED, en dernier.
    assert cause(attendu, revoquee=True) is ExclusionCause.REVOKED


def test_l_ordre_des_confirmations_ne_change_rien() -> None:
    """Ni le statut, ni les diagnostics — quel que soit l'ordre d'arrivee.

    Un rapport dont les lignes changent de place d'une execution a l'autre est
    illisible en comparaison, et comparer est exactement ce qu'un audit fait.
    """
    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1")
    b = confirmation(verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2")
    divergente = confirmation(
        verifier="chloe", cid="FICTIF-c3", cle="FICTIF-k3",
        package=paquet(edition_annexe="2018"),
    )
    etrangere = confirmation(
        verifier="david", cid="FICTIF-c4", cle="FICTIF-k4",
        package=paquet(rule_id="be.ec2.s_t_max",
                       spec=digest_of(payload_de_spec("be.ec2.s_t_max"))),
    )
    lot = [a, b, divergente, etrangere]

    reference = evalue(lot)
    for permutation in (
        [etrangere, divergente, b, a],
        [b, etrangere, a, divergente],
        [divergente, a, etrangere, b],
    ):
        autre = evalue(permutation)
        assert autre.status is reference.status
        assert autre.regards == reference.regards
        assert autre.excluded == reference.excluded, (
            "les diagnostics doivent sortir dans un ordre stable"
        )


def test_aucune_valeur_attendue_n_est_deduite_de_la_premiere_confirmation() -> None:
    """Exigence 10 — le sujet attendu vient du paquet, et de lui seul.

    Si la moindre valeur etait deduite des attestations, un lot ne contenant
    QUE des attestations etrangeres se replierait sur leur sujet et les
    declarerait concordantes.
    """
    attendu = paquet()
    etrangeres = tuple(
        confirmation(
            verifier=n, cid=f"FICTIF-c{i}", cle=f"FICTIF-k{i}",
            package=paquet(rule_id="be.ec2.s_t_max",
                           spec=digest_of(payload_de_spec("be.ec2.s_t_max"))),
        )
        for i, n in enumerate(("alice", "bob"))
    )
    verdict = evalue(etrangeres, attendu=attendu)

    assert verdict.status is ConfirmationStatus.UNCONFIRMED
    assert verdict.subject == attendu.subject_key
    assert verdict.regards == frozenset()
    assert len(verdict.excluded) == 2
    assert {e.cause for e in verdict.excluded} == {ExclusionCause.OTHER_SUBJECT}

    # Et le sujet annonce est identique a celui d'une evaluation SANS aucune
    # attestation: rien n'a ete emprunte au lot.
    assert evalue((), attendu=attendu).subject == verdict.subject


def test_une_confirmation_d_un_autre_pays_norme_ou_partie_n_est_jamais_comptee(
) -> None:
    """Exigence 3 de 6.3a2."""
    for remplacements in (
        {"country_code": "FR"},
        {"standard_family": "EN 1993"},
        {"part": "1-2"},
    ):
        etranger = paquet(**remplacements)
        c = confirmation(package=etranger)
        verdict = evalue((c,), politique=ConfirmationPolicy("test", 1))
        assert verdict.status is ConfirmationStatus.UNCONFIRMED, remplacements
        (exclue,) = verdict.excluded
        assert exclue.cause is ExclusionCause.OTHER_SUBJECT


def test_le_paquet_refuse_un_dossier_incomplet() -> None:
    """Le defaut que 6.3a2 existe pour empecher.

    Deux verificateurs peuvent tres bien s'accorder sur un dossier auquel il
    manque une couche. Le paquet le refuse **avant** toute signature.
    """
    for manquante in range(len(required_sources(SPEC))):
        with pytest.raises(ConfirmationDomainError, match="INCOMPLET"):
            paquet(items=dossier_pour(SPEC, sauf=manquante))


def test_le_paquet_refuse_une_preuve_etrangere_a_la_specification() -> None:
    """L'autre sens: une preuve tiree d'un document hors pile."""
    etrangere = dataclasses.replace(
        dossier_complet()[0], document_digest=DOC_ETRANGER,
    )
    with pytest.raises(ConfirmationDomainError,
                       match="aucune source declaree"):
        paquet(items=(*dossier_complet(), etrangere))


def test_le_paquet_recalcule_sa_cle_et_son_empreinte_de_preuve() -> None:
    """Exigence 6 — ni l'une ni l'autre ne peut etre falsifiee."""
    p = paquet()
    assert p.evidence == evidence_digest(p.evidence_items)
    assert p.subject_key.evidence_digest == p.evidence.digest
    assert p.subject_key.stack_digest == p.stack.digest.digest

    for champ in ("evidence", "subject_key"):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(p, champ, digest_of({"faux": True}))

    # Et l'appelant ne peut meme pas les FOURNIR — ni l'une, ni l'autre.
    # Les deux sont verifiees separement: rendre `subject_key` fournissable
    # tout en gardant `evidence` calculee laisserait passer une cle falsifiee.
    faux_sujet = dataclasses.replace(p.subject_key, rule_id="be.ec2.autre")
    for interdit in ({"evidence": digest_of({"faux": True})},
                     {"subject_key": faux_sujet}):
        with pytest.raises(TypeError):
            NormativeReviewPackage(
                package_version="esc-review-package/1", country_code="BE",
                standard_family="EN 1992", part="1-1",
                rule_id="be.ec2.nu_strength_reduction", stack=pile(),
                normative_spec=SPEC, implementation=IMPL,
                evidence_items=dossier_complet(), **interdit,
            )


def test_modifier_un_element_de_preuve_change_le_sujet_attendu() -> None:
    """Exigence 7."""
    base = paquet()
    sources = required_sources(SPEC)
    for modifie in (
        # un folio different
        (preuve_pour(sources[0], page=105), preuve_pour(sources[1])),
        # une citation differente
        (preuve_pour(sources[0]),
         preuve_pour(sources[1], citation="FICTIF — autre citation.")),
    ):
        assert paquet(items=modifie).subject_key != base.subject_key


def test_le_paquet_refuse_une_regle_qui_n_est_pas_celle_de_la_specification(
) -> None:
    """Presenter une regle sous le nom d'une autre."""
    with pytest.raises(ConfirmationDomainError, match="annonce la regle"):
        paquet(rule_id="be.ec2.s_t_max")          # SPEC porte un autre rule_id


def test_le_paquet_refuse_une_pile_d_une_autre_juridiction() -> None:
    with pytest.raises(ConfirmationDomainError, match="deux referentiels"):
        NormativeReviewPackage.of(
            country_code="FR", standard_family="EN 1992", part="1-1",
            rule_id="be.ec2.nu_strength_reduction", stack=pile(),
            normative_spec=SPEC, implementation=IMPL,
            evidence_items=dossier_complet(),
        )


def test_les_sources_requises_se_lisent_dans_le_payload_de_specification(
) -> None:
    """La verification du lien sources/preuves est AUTOMATISEE, pas reportee.

    Elle est possible parce que ``normative_spec_digest`` conserve son payload
    canonique et qu'il porte, pour chaque couche et pour l'autorite, la
    reference ET l'empreinte du document.
    """
    sources = required_sources(SPEC)
    assert {s.document_digest for s in sources} == {DOC_BASE, DOC_ANB}
    assert {s.role for s in sources} == {"base", "annexe"}
    assert all(isinstance(s, RequiredSource) for s in sources)
    assert paquet().required_sources == sources

    # La cle de correspondance porte les cinq composantes demandees, et NON
    # l'effet, qui n'est que de la prose.
    base = next(s for s in sources if s.role == "base")
    assert base.match_key == (DOC_BASE, "FICTIF EN 1992-1-1", "base",
                              "§9.2.2", None)
    annexe = next(s for s in sources if s.role == "annexe")
    assert annexe.edition == "2010", "l'autorite declare son edition"


def test_une_version_de_canonicalisation_inconnue_est_refusee() -> None:
    """Plutot que d'interpreter au juge une structure qui a change."""
    ancien = payload_de_spec()
    ancien["canonicalization_version"] = "esc-canon/0"
    with pytest.raises(ConfirmationDomainError, match="version"):
        required_sources(digest_of(ancien))


def test_revoquer_puis_evaluer_ne_modifie_jamais_le_paquet() -> None:
    """Exigence 12 — le paquet est une entree, pas un accumulateur."""
    p = paquet()
    avant = (p.subject_key, p.evidence, dataclasses.astuple(p.subject_key))

    a = confirmation(verifier="alice", cid="FICTIF-c1", cle="FICTIF-k1",
                     package=p)
    b = confirmation(verifier="bob", cid="FICTIF-c2", cle="FICTIF-k2",
                     package=p)
    for revs in ((), (revocation(a),), (revocation(a), revocation(b))):
        evalue((a, b), revs, attendu=p)

    assert (p.subject_key, p.evidence, dataclasses.astuple(p.subject_key)) == avant
    assert p.evidence_items == dossier_complet()


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
        package=paquet(rule_id="be.ec2.s_t_max",
                       spec=digest_of(payload_de_spec("be.ec2.s_t_max"))),
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
    verdict = evalue(
        p.confirmations_for(cs[0].rule_id),
        p.revocations_for(cs[0].rule_id),
    )
    assert len(verdict.regards) == 3
    assert verdict.is_confirmed


# ---------------------------------------------------------------------------
# Concordance avec une VRAIE regle
#
# Le module de domaine ne doit pas dependre du registre des regles — un test
# le verifie plus bas. Rien n'empeche en revanche CE fichier d'aller chercher
# une vraie regle pour montrer que le mecanisme tient sur des donnees reelles.
# Aucune confirmation n'y est creee: un paquet de revue n'est pas une
# attestation, c'est ce qu'on presenterait a un relecteur.
# ---------------------------------------------------------------------------
def _regle_reelle():
    from eurostruct_engine.ndp import rules_be_ec2 as reelles
    from eurostruct_engine.ndp.canonical import (
        implementation_digest,
        normative_spec_digest,
    )

    regle = reelles.RHO_W_MIN
    return regle, normative_spec_digest(regle), implementation_digest(regle)


def _paquet_reel(items):
    regle, spec, impl = _regle_reelle()
    sources = required_sources(spec)
    return NormativeReviewPackage.of(
        country_code="BE", standard_family="EN 1992", part="1-1",
        rule_id=regle.rule_id,
        stack=NormativeStack.of(
            country_code="BE", standard_family="EN 1992", part="1-1",
            components=tuple(
                NormativeStackComponent(
                    s.role, s.reference, s.edition or "2010", i + 1,
                    s.document_digest,
                )
                for i, s in enumerate(sources)
            ),
        ),
        normative_spec=spec, implementation=impl, evidence_items=items,
    )


def test_quatre_sources_sur_trois_documents_pour_be_ec2_rho_w_min() -> None:
    """Le cas reel qui a motive ce correctif.

    `be.ec2.rho_w_min` declare QUATRE sources reparties sur TROIS documents:
    le corps de l'EN et le corrigendum AC:2008 sont relies dans le meme PDF
    belge et partagent donc leur empreinte.
    """
    _, spec, _ = _regle_reelle()
    sources = required_sources(spec)

    assert len(sources) == 4
    assert len({s.document_digest for s in sources}) == 3
    assert len({s.match_key for s in sources}) == 4, (
        "quatre sources doivent rester quatre: si deux se confondent, une "
        "preuve unique en couvrirait deux"
    )
    partagees = [s for s in sources
                 if s.document_digest == sources[0].document_digest]
    assert {s.role for s in partagees} == {"base", "corrigendum"}


def test_une_preuve_par_document_ne_suffit_pas_sur_une_vraie_regle() -> None:
    """Trois preuves pour quatre sources: REFUS.

    C'est exactement ce que l'ancienne couverture par documents acceptait — et
    ce que le test « quatre sources, trois documents » de 6.3a2 documentait
    sans l'attraper.
    """
    _, spec, _ = _regle_reelle()
    sources = required_sources(spec)

    vues: set[str] = set()
    une_par_document = []
    for i, src in enumerate(sources):
        if src.document_digest not in vues:
            vues.add(src.document_digest)
            une_par_document.append(preuve_pour(src, page=100 + i))
    assert len(une_par_document) == 3

    with pytest.raises(ConfirmationDomainError, match="INCOMPLET"):
        _paquet_reel(tuple(une_par_document))


def test_une_preuve_par_source_convient_sur_une_vraie_regle() -> None:
    """Quatre preuves, une par source: accepte, et la cle est celle de la regle."""
    regle, spec, impl = _regle_reelle()
    sources = required_sources(spec)
    p = _paquet_reel(tuple(
        preuve_pour(src, page=100 + i) for i, src in enumerate(sources)
    ))
    assert p.subject_key.rule_id == regle.rule_id
    assert p.subject_key.normative_spec_digest == spec.digest
    assert p.subject_key.implementation_digest == impl.digest
    assert p.subject_key.evidence_digest == p.evidence.digest


@pytest.mark.parametrize(
    ("ecart", "quoi"),
    [
        ({"clause": "§9.9.9"}, "clause"),
        ({"document_role": "reglement"}, "role"),
        ({"reference": "FICTIF autre reference"}, "reference"),
    ],
    ids=["mauvaise_clause", "mauvais_role", "mauvaise_reference"],
)
def test_une_preuve_mal_rattachee_est_refusee_sur_une_vraie_regle(
    ecart, quoi,
) -> None:
    """Bon document, mais rattache a autre chose que ce qu'il prouve.

    Le systeme ne juge pas si la citation est intellectuellement correcte —
    c'est le travail du verificateur. Il empeche seulement qu'elle soit
    rattachee a une autre source structuree.
    """
    _, spec, _ = _regle_reelle()
    sources = required_sources(spec)
    items = [preuve_pour(src, page=100 + i) for i, src in enumerate(sources)]
    items[0] = preuve_pour(sources[0], page=100, **ecart)

    with pytest.raises(ConfirmationDomainError):
        _paquet_reel(tuple(items))


def test_une_mauvaise_edition_est_refusee_quand_la_source_en_declare_une(
) -> None:
    """L'autorite normative declare son edition; les couches n'en declarent pas.

    L'edition n'est donc comparee que la ou elle existe — la comparer partout
    reviendrait a exiger une valeur que le referentiel ne fournit pas.
    """
    _, spec, _ = _regle_reelle()
    sources = required_sources(spec)
    avec_edition = [s for s in sources if s.edition is not None]
    sans_edition = [s for s in sources if s.edition is None]
    assert avec_edition and sans_edition, "les deux cas doivent exister"

    # La source qui declare une edition: un ecart d'edition est refuse.
    idx = sources.index(avec_edition[0])
    items = [preuve_pour(src, page=100 + i) for i, src in enumerate(sources)]
    items[idx] = preuve_pour(avec_edition[0], page=100, edition="1999")
    with pytest.raises(ConfirmationDomainError, match="INCOMPLET"):
        _paquet_reel(tuple(items))

    # Celle qui n'en declare pas: l'edition de la preuve est libre.
    idx = sources.index(sans_edition[0])
    items = [preuve_pour(src, page=100 + i) for i, src in enumerate(sources)]
    items[idx] = preuve_pour(sans_edition[0], page=100, edition="1999")
    _paquet_reel(tuple(items))          # ne leve pas


# --- le meme PDF portant deux couches, en fixture controlee ----------------
def test_base_et_corrigendum_dans_le_meme_pdf_restent_deux_sources() -> None:
    """Meme ``document_digest``, deux couches normatives distinctes."""
    sources = required_sources(SPEC_PDF_PARTAGE)
    partagees = [s for s in sources if s.document_digest == DOC_BASE]
    assert len(partagees) == 2
    assert {s.role for s in partagees} == {"base", "corrigendum"}
    assert len({s.match_key for s in partagees}) == 2


def test_une_preuve_de_la_base_ne_couvre_pas_le_corrigendum() -> None:
    """La propriete centrale de ce correctif.

    Une preuve du corps de la norme ne couvre pas le corrigendum, meme relie
    dans le meme fichier.
    """
    sources = required_sources(SPEC_PDF_PARTAGE)
    base = next(s for s in sources if s.role == "base")
    autres = [s for s in sources if s.role != "corrigendum"]

    # Toutes les sources SAUF le corrigendum: refus.
    items = tuple(preuve_pour(s, page=100 + i) for i, s in enumerate(autres))
    with pytest.raises(ConfirmationDomainError, match="INCOMPLET"):
        paquet(spec=SPEC_PDF_PARTAGE, items=items)

    # Dupliquer la preuve de la base ne comble rien: elle porte le role 'base'.
    doublon = (*items, preuve_pour(base, page=777))
    with pytest.raises(ConfirmationDomainError, match="INCOMPLET"):
        paquet(spec=SPEC_PDF_PARTAGE, items=doublon)

    # Une preuve par source: accepte.
    complet = tuple(
        preuve_pour(s, page=100 + i) for i, s in enumerate(sources)
    )
    assert paquet(spec=SPEC_PDF_PARTAGE, items=complet).subject_key


def test_deux_sources_indistinguables_par_leur_cle_sont_refusees() -> None:
    """``expression_label`` ne peut pas entrer dans la cle: refus explicite.

    ``EvidenceItem`` n'a aucun champ ou exprimer le label d'une expression, et
    lui en ajouter un changerait ``evidence_digest``, donc la canonicalisation.
    Plutot que de laisser une preuve en couvrir deux au hasard, le paquet
    refuse — la verification est reportee, pas inventee.
    """
    ambigu = digest_of(payload_de_spec(labels_ambigus=True))
    sources = required_sources(ambigu)
    with pytest.raises(ConfirmationDomainError, match="expressions differentes"):
        paquet(spec=ambigu, items=tuple(
            preuve_pour(s, page=100 + i) for i, s in enumerate(sources)
        ))


# ---------------------------------------------------------------------------
# Integrite des Digest
# ---------------------------------------------------------------------------
def test_un_digest_ne_peut_pas_porter_un_hash_qui_ne_resume_pas_son_payload(
) -> None:
    """Les deux falsifications symetriques, toutes deux indetectables autrement.

    Une structure immuable construite avec un faux hash reste fausse: geler un
    mensonge n'en fait pas une preuve.
    """
    from eurostruct_engine.ndp.canonical import DigestIntegrityError

    bon = digest_of({"a": 1})

    # payload modifie sans recalcul du hash
    with pytest.raises(DigestIntegrityError, match="calculee sur le payload"):
        dataclasses.replace(bon, canonical_payload='{"a":2}')

    # hash modifie sans modification du payload
    with pytest.raises(DigestIntegrityError, match="calculee sur le payload"):
        dataclasses.replace(bon, digest="0" * 64)

    # algorithme inconnu: refuse plutot qu'accepte sans controle
    with pytest.raises(DigestIntegrityError, match="inconnu"):
        dataclasses.replace(bon, algorithm="md5")


def test_les_digests_du_paquet_sont_integres_par_construction() -> None:
    """La garantie couvre les quatre empreintes que le paquet manipule.

    Elle est posee a la construction de ``Digest`` plutot que chez chaque
    consommateur: un consommateur qui oublierait de verifier est exactement le
    chemin par lequel un faux hash circulerait.
    """
    import hashlib

    p = paquet()
    for empreinte in (p.normative_spec, p.implementation, p.evidence,
                      p.stack.digest):
        attendu = hashlib.sha256(
            empreinte.canonical_payload.encode("utf-8")
        ).hexdigest()
        assert empreinte.digest == attendu
        assert empreinte.algorithm == "sha256"


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
