"""Du quatre-yeux consommé jusqu'au portillon du mode strict.

CE QUI MANQUAIT, ET POURQUOI C'ÉTAIT LE TROU CENTRAL
-----------------------------------------------------
Tout existait sauf le fil qui relie les deux bouts :

* PostgreSQL sait proposer, approuver par un second principal, consommer une
  fois — et refuser le rejeu ;
* ``assess_confirmations`` sait confronter des attestations au dossier qui
  devait leur être présenté ;
* ``ParameterSet.preflight`` sait refuser un paramètre non confirmé.

Mais **rien n'appelait ``assess_confirmations`` sur le chemin réel du calcul**.
Le mode strict lisait ``validation_status`` dans un fichier JSON du dépôt, et
rien d'autre. La racine de confiance était complète et débranchée : une
garantie que rien n'exerce ne se distingue pas d'une garantie perdue.

CE QUE CE MODULE FAIT, ET DANS QUEL ORDRE
------------------------------------------
1. il reçoit le **dossier de revue** — ce qui a été présenté aux deux
   ingénieurs — et le confronte à ce que le registre détient ;
2. il demande au provider les confirmations et les révocations de ce sujet ;
3. il appelle ``assess_confirmations``, sans rien réinterpréter ;
4. **seulement si** le verdict est ``CONFIRMED``, il superpose le statut sur
   **ce paramètre-là** dans le jeu de paramètres.

CE QU'IL NE FAIT SURTOUT PAS
-----------------------------
**Il ne construit pas le dossier attendu.** Il serait tentant de le dériver du
registre : on aurait alors un système qui écrit lui-même la question puis
vérifie qu'on y a répondu. Le dossier est un fait historique — ce que deux
personnes ont eu sous les yeux — et il vient d'où il a été produit.

**Il ne devine aucune valeur.** Le dossier prétend porter sur une valeur ; le
registre en détient une. Si les deux diffèrent, le paramètre n'est pas
confirmé : il est **refusé**, et le rapport dit laquelle des deux ne
correspond pas. Un dossier signé sur ``alpha_cc = 1,00`` ne confirme pas un
registre qui porte ``0,85``.

**Il n'ouvre rien par « meilleur effort ».** Chaque écart est un refus. Il n'y
a pas de correspondance partielle, pas de tolérance sur l'édition, pas de
« probablement le même document ».

**Une proposition ne suffit pas ; un seul signataire ne suffit pas ; une
approbation non consommée ne suffit pas.** Ces trois-là ne sont pas vérifiés
ici et c'est délibéré : ils sont vrais **par construction**. Le provider ne
rend que des confirmations écrites, et une confirmation n'est écrite qu'au
bout du chemin d'autorité — PostgreSQL s'en porte garant par contrainte de
table. Le compte de regards indépendants, lui, est la politique, appliquée par
``assess_confirmations``.

CE QUE ÇA CHANGE POUR LES 29 VALEURS D'AUJOURD'HUI
---------------------------------------------------
Rien. Aucune n'a de confirmation en base, donc chacune reste bloquée, et le
calcul strict continue de refuser partout. C'est le comportement voulu : ce
module ne rend pas le strict possible, il rend possible **qu'il le devienne**,
par le seul chemin qui vaille.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from .canonical import CANONICALIZATION_VERSION, canonical_json
from .confirmation import (
    ConfirmationDomainError,
    ConfirmationPolicy,
    ConfirmationProvider,
    ConfirmationStatus,
    NormativeReviewPackage,
    assess_confirmations,
)
from .implementation import empreinte_implementation
from .model import ValidationStatus

if TYPE_CHECKING:  # pragma: no cover - typage seul
    from .model import NationalParameter
    from .registry import ParameterSet

__all__ = [
    "POLITIQUE_PAR_DEFAUT",
    "RapportPasserelle",
    "appliquer_confirmations",
    "confirmer_depuis_le_provider",
    "evaluer_depuis_le_provider",
    "evaluer_parametre",
    "paquet_presente",
]

#: Deux regards indépendants. C'est la règle du quatre-yeux, énoncée là où on
#: peut la lire, et non une constante enfouie dans un appel.
POLITIQUE_PAR_DEFAUT = ConfirmationPolicy(
    policy_version="esc-policy/2-yeux",
    minimum_independent_confirmations=2,
)


@dataclass(frozen=True, slots=True)
class RapportPasserelle:
    """Ce que la passerelle a constaté pour un paramètre, et pourquoi.

    ``usable`` est le seul champ qui décide. Les autres existent pour que le
    refus soit **lisible** : un portillon qui dit non sans dire lequel des huit
    contrôles a échoué est un portillon que personne ne peut franchir.
    """

    key: str
    #: ``None`` quand le dossier n'a même pas pu être confronté — il ne portait
    #: pas sur ce paramètre. Il n'y a alors pas de verdict d'attestation à
    #: rendre : la question n'a pas été posée.
    status: ConfirmationStatus | None
    reason: str
    verifiers: frozenset[str]

    @property
    def usable(self) -> bool:
        return self.status is ConfirmationStatus.CONFIRMED

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "status": self.status.value if self.status else "no_package",
            "reason": self.reason,
            "verifiers": sorted(self.verifiers),
            "usable_in_strict_mode": self.usable,
        }


def _refus(key: str, raison: str) -> RapportPasserelle:
    return RapportPasserelle(key=key, status=None, reason=raison,
                             verifiers=frozenset())


def _canonique(valeur: Any) -> Any:
    """La forme canonique d'une valeur, telle que le payload la porte.

    La canonicalisation enveloppe les flottants — ``0.85`` devient
    ``{"__float__": "0.85"}`` — pour qu'un nombre ne dépende pas de la
    représentation textuelle de la plateforme. Comparer la valeur Python nue
    au champ du payload rendrait donc **toujours** faux, et le contrôle de
    valeur refuserait tout, y compris ce qui correspond. On passe les deux
    côtés par la même moulinette.
    """
    return json.loads(canonical_json(valeur))


def _payload_de_spec(paquet: NormativeReviewPackage) -> dict[str, Any]:
    """Le payload canonique de la spécification, relu depuis l'empreinte.

    C'est possible parce que ``Digest`` conserve son payload — et le vérifie à
    la construction. On ne fait donc pas confiance à une empreinte : on lit ce
    qu'elle résume, et l'empreinte prouve que c'est bien cela.
    """
    charge = json.loads(paquet.normative_spec.canonical_payload)
    if charge.get("canonicalization_version") != CANONICALIZATION_VERSION:
        raise ConfirmationDomainError(
            f"payload de specification en version "
            f"{charge.get('canonicalization_version')!r}, attendu "
            f"{CANONICALIZATION_VERSION!r}. Interpreter une structure dont la "
            "forme a change reviendrait a inventer une garantie."
        )
    return charge


def _ecart_de_sujet(parametre: NationalParameter,
                    paquet: NormativeReviewPackage) -> str | None:
    """Ce dossier porte-t-il **exactement** sur ce paramètre du registre ?

    Huit contrôles, et aucun n'est décoratif. Chacun répond à une façon
    différente pour un dossier signé de bonne foi de ne pas parler du
    paramètre qu'on s'apprête à débloquer.
    """
    attendus = (
        ("pays", parametre.country_code, paquet.country_code),
        ("famille de norme", parametre.standard_family, paquet.standard_family),
        ("partie", parametre.part, paquet.part),
        ("regle", parametre.key, paquet.rule_id),
    )
    for nom, registre, dossier in attendus:
        if registre != dossier:
            return (f"{nom}: le registre porte {registre!r} et le dossier de "
                    f"revue {dossier!r}. Un dossier qui ne parle pas de ce "
                    "parametre ne peut pas le confirmer.")

    try:
        charge = _payload_de_spec(paquet)
    except ConfirmationDomainError as cause:
        return str(cause)

    # --- LA VALEUR ELLE-MEME ------------------------------------------------
    # Le contrôle qui compte le plus. Sans lui, deux ingénieurs pourraient
    # signer en toute bonne foi un dossier portant 1,00 et débloquer un
    # registre portant 0,85 — la signature serait authentique et le nombre
    # utilisé ne serait pas celui qui a été relu.
    valeur = charge.get("scalar_value")
    if valeur != _canonique(parametre.parameter_value):
        return (f"valeur: le registre porte {parametre.parameter_value!r} et "
                f"le dossier signe {valeur!r}. Deux ingenieurs ont pu signer "
                "de bonne foi: ils n'ont pas relu ce nombre-la.")

    unite = charge.get("output_unit")
    if unite != parametre.unit:
        return (f"unite: le registre porte {parametre.unit!r} et le dossier "
                f"{unite!r}.")

    provenance = charge.get("value_provenance")
    if provenance != parametre.value_provenance.value:
        return (f"provenance: le registre porte "
                f"{parametre.value_provenance.value!r} et le dossier "
                f"{provenance!r}. Une valeur reprise de la Note du Eurocode "
                "n'est pas une valeur nationale, meme signee deux fois.")

    # --- L'AUTORITE NORMATIVE, ET LE DOCUMENT REELLEMENT LU -----------------
    autorite = charge.get("normative_authority") or {}
    if autorite.get("reference") != parametre.national_annex_reference:
        return (f"annexe: le registre cite "
                f"{parametre.national_annex_reference!r} et le dossier "
                f"{autorite.get('reference')!r}.")
    if autorite.get("edition") != parametre.edition:
        return (f"edition: le registre porte {parametre.edition!r} et le "
                f"dossier {autorite.get('edition')!r}. La meme regle "
                "confirmee pour deux editions fait deux sujets, tous deux "
                "legitimes — et un seul s'applique ici.")

    # L'EMPREINTE DU DOCUMENT DEPOSE. Sans elle, rien ne relie la signature au
    # fichier qui était sur l'écran du relecteur.
    if not parametre.source_doc_id:
        return ("le registre ne porte aucune empreinte du document source "
                "(source_doc_id). Une confirmation ne peut pas etre rattachee "
                "au fichier qui a ete lu, et on ne la fabrique pas.")
    if autorite.get("document_digest") != parametre.source_doc_id:
        return (f"document: le registre porte l'empreinte "
                f"{parametre.source_doc_id[:16]}… et le dossier "
                f"{str(autorite.get('document_digest'))[:16]}…. Ce n'est pas "
                "le meme fichier.")

    # --- LA PILE DOIT CONTENIR CE DOCUMENT, A CETTE EDITION -----------------
    etages = [c for c in paquet.stack.components
              if c.document_digest == parametre.source_doc_id]
    if not etages:
        return ("la pile normative du dossier ne contient pas le document du "
                "registre: la signature porte sur une autre pile.")
    if all(c.edition != parametre.edition for c in etages):
        return (f"la pile porte ce document a une autre edition que "
                f"{parametre.edition!r}.")

    # --- L'IMPLEMENTATION REELLEMENT DEPLOYEE -------------------------------
    #
    # LE CONTROLE QUI MANQUAIT, ET IL EST DU MEME ORDRE QUE CELUI DE LA VALEUR.
    #
    # Une confirmation dit trois choses: quelle regle, quelle valeur, et QUEL
    # CODE l'applique. Les deux premieres etaient ancrees au registre; la
    # troisieme ne l'etait a rien. `implementation_payload` se construisait a
    # partir d'un texte fourni par le client, si bien que:
    #
    #   * deux redactions du meme parametre donnaient deux empreintes — donc
    #     deux sujets pour un seul code;
    #   * le code pouvait changer entierement sans qu'aucune confirmation cesse
    #     d'etre valable.
    #
    # On RECALCULE donc l'empreinte ici, independamment, depuis le chemin de
    # code declare et la version du moteur qui tourne. Une confirmation
    # antérieure reste dans l'historique — elle est authentique et l'audit la
    # voit — et n'ouvre plus rien.
    try:
        attendue = empreinte_implementation(parametre.key)
    except ConfirmationDomainError as cause:
        return str(cause)
    if paquet.implementation.digest != attendue.digest:
        return (
            f"implementation: le dossier atteste du code "
            f"{paquet.implementation.digest[:16]}… et le moteur qui tourne "
            f"porte {attendue.digest[:16]}…. La confirmation reste dans "
            "l'historique — elle a eu lieu — mais elle atteste d'un code "
            "revolu: elle n'ouvre plus le mode strict. Refaire passer ce "
            "parametre par le chemin d'autorite."
        )

    return None


def evaluer_parametre(
    parametre: NationalParameter,
    paquet: NormativeReviewPackage | None,
    *,
    provider: ConfirmationProvider,
    policy: ConfirmationPolicy = POLITIQUE_PAR_DEFAUT,
) -> RapportPasserelle:
    """Confronte un paramètre du registre aux attestations qui le visent.

    Rend un rapport, ne lève pas : un paramètre non confirmé n'est pas une
    exception, c'est l'état ordinaire de ce référentiel aujourd'hui.
    """
    cle = parametre.key

    if paquet is None:
        return _refus(cle, "aucun dossier de revue n'a ete presente pour ce "
                           "parametre. Sans dossier, il n'y a rien a confirmer.")

    ecart = _ecart_de_sujet(parametre, paquet)
    if ecart is not None:
        return _refus(cle, ecart)

    # LE PROVIDER EST LA FRONTIERE. Il ne rend que des confirmations ECRITES,
    # et une confirmation n'est ecrite qu'au bout du chemin d'autorite: une
    # proposition seule, une approbation non consommee ou un rejeu n'y sont
    # jamais arrivees. On ne le revérifie pas ici — deux verifications
    # concurrentes, c'est une de trop, et c'est toujours la plus faible qui
    # finit par decider.
    confirmations = provider.confirmations_for(paquet.rule_id)
    revocations = provider.revocations_for(paquet.rule_id)

    evaluation = assess_confirmations(
        expected=paquet,
        confirmations=confirmations,
        revocations=revocations,
        policy=policy,
    )
    return RapportPasserelle(
        key=cle,
        status=evaluation.status,
        reason=evaluation.reason,
        verifiers=frozenset(evaluation.regards),
    )


def appliquer_confirmations(
    jeu: ParameterSet,
    paquets: Mapping[str, NormativeReviewPackage],
    *,
    provider: ConfirmationProvider,
    policy: ConfirmationPolicy = POLITIQUE_PAR_DEFAUT,
) -> tuple[ParameterSet, tuple[RapportPasserelle, ...]]:
    """Rend un jeu où **seuls** les paramètres confirmés sont utilisables.

    LA SUPERPOSITION EST LA PARTIE DANGEREUSE, et elle est donc la plus
    étroite possible :

    * elle ne touche **que** les paramètres pour lesquels un dossier a été
      présenté **et** dont l'évaluation rend ``CONFIRMED`` ;
    * elle ne change **que** ``validation_status`` — jamais la valeur, jamais
      l'unité, jamais la provenance. Le nombre utilisé reste celui du registre,
      et c'est précisément celui sur lequel les deux ingénieurs ont signé,
      puisque l'écart aurait été refusé plus haut ;
    * elle rend un **nouveau** jeu. L'original n'est pas modifié : un appelant
      qui n'est pas passé par ici continue de voir le référentiel tel qu'il
      est, et aucun effet de bord ne peut fuir vers une autre requête.

    Les rapports sont rendus **pour tous** les paquets présentés, y compris
    ceux qui ont été refusés : c'est la liste de travail de l'ingénieur.
    """
    rapports: list[RapportPasserelle] = []
    confirmes: set[tuple[str, str]] = set()

    for cle, paquet in sorted(paquets.items()):
        parametre = jeu.find(cle)
        if parametre is None:
            rapports.append(_refus(
                cle, "aucun parametre de ce nom n'est en vigueur a la date de "
                     "reference: un dossier ne peut pas confirmer ce que le "
                     "registre ne detient pas."))
            continue
        rapport = evaluer_parametre(parametre, paquet, provider=provider,
                                    policy=policy)
        rapports.append(rapport)
        if rapport.usable:
            confirmes.add((cle, parametre.edition))

    if not confirmes:
        return jeu, tuple(rapports)
    return _jeu_superpose(jeu, confirmes), tuple(rapports)


def _jeu_superpose(jeu: ParameterSet,
                   confirmes: set[tuple[str, str]]) -> ParameterSet:
    """Reconstruit le jeu avec les seuls statuts confirmés modifiés.

    La correspondance porte sur ``(clé, édition)``. Le registre conserve les
    éditions successives d'une annexe : ne comparer que la clé ouvrirait
    toutes les éditions d'un paramètre dès qu'une seule a été relue.
    """
    annexes = []
    for annexe in jeu.registry.annexes:
        parametres = tuple(
            replace(p, validation_status=ValidationStatus.CONFIRMED)
            if (p.key, p.edition) in confirmes and p.is_in_force(jeu.as_of)
            else p
            for p in annexe.parameters
        )
        annexes.append(replace(annexe, parameters=parametres))

    return replace(
        jeu, registry=replace(jeu.registry, annexes=tuple(annexes)),
    )


# ---------------------------------------------------------------------------
# LE CHEMIN REEL: SANS PAQUET FOURNI, ON LE RELIT DANS L'ATTESTATION
# ---------------------------------------------------------------------------
def paquet_presente(
    confirmation: Any,
) -> NormativeReviewPackage:
    """Le dossier qui a été présenté, reconstruit depuis une attestation.

    POURQUOI C'EST POSSIBLE. Une confirmation porte déjà tout ce qui compose
    le paquet : pays, famille, partie, règle, pile normative, empreinte de
    spécification, empreinte d'implémentation et dossier de preuve. Le
    provider PostgreSQL les relit colonne par colonne et **vérifie** au passage
    que la pile reconstruite redonne bien ``stack_digest`` et le dossier
    ``evidence_digest`` — une attestation dont le contenu aurait bougé ne se
    projette pas.

    CE QUE CETTE RECONSTRUCTION NE PROUVE PAS, ET IL FAUT LE DIRE. Le paquet
    vient alors d'une **attestation**, pas d'une source indépendante d'elle.
    Deux vérificateurs qui s'entendraient définiraient donc leur propre sujet.

    C'est le point où la garantie ne vient plus de la forme mais du fond, et
    elle vient d'ailleurs : :func:`_ecart_de_sujet` confronte ce paquet au
    **registre**, qui n'est pas sous leur contrôle. Deux signataires peuvent
    convenir d'un dossier ; ils ne peuvent pas lui faire dire une valeur, une
    provenance, une édition ou une empreinte de document que le registre ne
    porte pas. Et le quatre-yeux, lui, exige qu'ils soient deux — c'est
    précisément la confiance que ce dispositif accorde à deux ingénieurs
    habilités, et pas davantage.
    """
    return NormativeReviewPackage.of(
        country_code=confirmation.country_code,
        standard_family=confirmation.standard_family,
        part=confirmation.part,
        rule_id=confirmation.rule_id,
        stack=confirmation.stack,
        normative_spec=confirmation.normative_spec,
        implementation=confirmation.implementation,
        evidence_items=confirmation.evidence_items,
    )


def evaluer_depuis_le_provider(
    parametre: NationalParameter,
    *,
    provider: ConfirmationProvider,
    policy: ConfirmationPolicy = POLITIQUE_PAR_DEFAUT,
) -> RapportPasserelle:
    """Évalue un paramètre **sans qu'aucun paquet ne soit fourni**.

    C'est la forme qu'appelle le chemin de calcul : il connaît le paramètre et
    le provider, et rien d'autre.

    ON EXAMINE TOUS LES DOSSIERS DISTINCTS, PAS LE PREMIER
    -------------------------------------------------------
    Une rédaction antérieure retenait ``confirmations[0]`` comme dossier
    candidat. Une attestation portant sur autre chose — une édition ancienne,
    une valeur erronée, un dossier qu'on a refusé de retenir — **empoisonnait
    définitivement** une paire correcte plus récente : le candidat ne
    correspondait pas au registre, l'évaluation s'arrêtait là, et le paramètre
    restait bloqué quoi qu'on signe ensuite. Le parcours de bout en bout l'a
    produit tout seul, dès que des cas négatifs eurent laissé leurs
    attestations dans la table.

    On regroupe donc les attestations par **sujet signé**, et on évalue chaque
    dossier distinct. L'ordre des lignes rendues par SQL ne change rien : les
    candidats sont triés sur leur sujet, et il suffit qu'**un** d'entre eux
    corresponde au registre et satisfasse la politique.
    """
    confirmations = provider.confirmations_for(parametre.key)
    if not confirmations:
        return RapportPasserelle(
            key=parametre.key,
            status=ConfirmationStatus.UNCONFIRMED,
            reason=("aucune attestation ne porte sur ce parametre. La "
                    "confirmation se fait par le chemin d'autorite: "
                    "proposition, approbation par un second ingenieur, "
                    "consommation."),
            verifiers=frozenset(),
        )

    # UN DOSSIER PAR SUJET SIGNE. Deux attestations du meme sujet decrivent le
    # meme dossier — c'est ce que `subject_key` veut dire.
    candidats: dict[tuple, NormativeReviewPackage] = {}
    illisibles = 0
    for c in confirmations:
        try:
            paquet = paquet_presente(c)
        except ConfirmationDomainError:
            # Une attestation dont le dossier ne se reconstruit pas ne peut
            # servir de candidat. Elle n'empeche pas les autres d'etre lues.
            illisibles += 1
            continue
        cle = _cle_de_tri(paquet)
        candidats.setdefault(cle, paquet)

    if not candidats:
        return _refus(
            parametre.key,
            f"les {illisibles} attestation(s) presentes portent des dossiers "
            "qui ne se reconstruisent pas.")

    ecarts: list[str] = []
    proches: list[RapportPasserelle] = []
    for _cle, paquet in sorted(candidats.items(), key=lambda kv: kv[0]):
        ecart = _ecart_de_sujet(parametre, paquet)
        if ecart is not None:
            ecarts.append(ecart)
            continue
        rapport = evaluer_parametre(parametre, paquet, provider=provider,
                                    policy=policy)
        if rapport.usable:
            return rapport      # un dossier exact et suffisant: c'est fini
        proches.append(rapport)

    # AUCUN DOSSIER N'OUVRE. On rend le refus LE PLUS INFORMATIF: un dossier
    # qui correspond au registre mais manque de regards apprend davantage
    # qu'un dossier qui parle d'autre chose.
    if proches:
        return proches[0]
    return _refus(
        parametre.key,
        f"{len(candidats)} dossier(s) atteste(s), aucun ne correspond au "
        f"registre. Premier ecart: {ecarts[0]}")


def _cle_de_tri(paquet: NormativeReviewPackage) -> tuple:
    """Un ordre TOTAL et stable sur les dossiers candidats.

    Sans lui, le verdict dependrait de l'ordre dans lequel PostgreSQL rend ses
    lignes — c'est-a-dire de rien de normatif.
    """
    s = paquet.subject_key
    return (s.country_code, s.standard_family, s.part, s.rule_id,
            s.stack_digest, s.normative_spec_digest, s.implementation_digest,
            s.evidence_digest)


def confirmer_depuis_le_provider(
    jeu: ParameterSet,
    cles: tuple[str, ...],
    *,
    provider: ConfirmationProvider,
    policy: ConfirmationPolicy = POLITIQUE_PAR_DEFAUT,
) -> tuple[ParameterSet, tuple[RapportPasserelle, ...]]:
    """Le point d'entrée du chemin de calcul.

    Rend le jeu de paramètres tel que le préflight doit le voir, et le rapport
    de chaque clé demandée. Aujourd'hui, sur le référentiel livré, chaque
    rapport dit ``UNCONFIRMED`` et le jeu ressort inchangé : c'est le fait
    produit, pas une limite de ce module.
    """
    rapports: list[RapportPasserelle] = []
    confirmes: set[tuple[str, str]] = set()
    for cle in cles:
        parametre = jeu.find(cle)
        if parametre is None:
            rapports.append(_refus(
                cle, "aucun parametre de ce nom n'est en vigueur a la date de "
                     "reference."))
            continue
        rapport = evaluer_depuis_le_provider(parametre, provider=provider,
                                             policy=policy)
        rapports.append(rapport)
        if rapport.usable:
            # L'IDENTITE EXACTE, PAS LA SEULE CLE. Le registre conserve les
            # editions successives d'une annexe: confirmer « alpha_cc »
            # ouvrirait toutes ses editions, y compris celles que personne n'a
            # relues.
            confirmes.add((cle, parametre.edition))

    if not confirmes:
        return jeu, tuple(rapports)
    return _jeu_superpose(jeu, confirmes), tuple(rapports)
