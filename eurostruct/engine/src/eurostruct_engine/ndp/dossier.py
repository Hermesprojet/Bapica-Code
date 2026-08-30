"""Le dossier de revue : ce que A propose et ce que B relit, mot pour mot.

POURQUOI LE SERVEUR LE COMPOSE, ET PAS LE NAVIGATEUR
----------------------------------------------------
Un dossier de revue est fait de quatre payloads canoniques, et le serveur les
re-hache pour produire les empreintes qui seront stockées. Si le navigateur les
composait, deux choses seraient perdues à la fois :

* la **valeur** et sa **provenance** viendraient de l'écran, donc de ce que
  quelqu'un a tapé, alors qu'elles doivent venir du registre — c'est
  exactement ce que l'interdiction n°2 refuse ;
* la sérialisation exacte deviendrait une affaire de client. Un JSON
  équivalent mais autrement ordonné ne se re-hacherait pas à la même valeur,
  et la projection qui reconstruit la pile depuis la base la rejetterait.

Ce module est donc la **seule** composition du dossier dans le produit. La
route HTTP l'appelle, et le harnais qui prouve le parcours complet l'appelle
aussi : il n'y a pas deux façons de fabriquer un dossier, donc pas deux
vérités.

CE QUE LE SERVEUR SAIT, ET CE QU'IL NE SAIT PAS
------------------------------------------------
Du registre, il tient tout ce qui est vérifiable : la valeur, l'unité, la
provenance, la référence de l'annexe, l'édition, la clause, l'empreinte du
document déposé, le folio imprimé.

Il ne tient PAS la **citation** — le texte exact lu dans l'annexe publiée — ni
la déclaration de ce que les deux ingénieurs certifient avoir contrôlé. Ces
deux-là sont le travail humain que le quatre-yeux existe pour encadrer, et les
inventer viderait le dispositif de son objet. Ils sont donc des paramètres
obligatoires : sans eux, ce module refuse plutôt que de composer un dossier
qui aurait l'air complet.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .canonical import (
    CANONICALIZATION_VERSION,
    Digest,
    EvidenceItem,
    digest_of,
    evidence_digest,
)
from .confirmation import (
    ConfirmationDomainError,
    NormativeStack,
    NormativeStackComponent,
    required_sources,
)
from .implementation import empreinte_implementation

__all__ = [
    "CitationDeRevue",
    "DossierCompose",
    "composer_dossier",
    "empreintes_des_payloads",
]


def empreintes_des_payloads(
    *, normative_spec_payload: str, implementation_payload: str,
    evidence_payload: str, stack_payload: str,
) -> dict[str, str]:
    """Re-hache quatre payloads relus. Ne fait confiance à aucune annonce.

    Sert au second regard : le dossier vient d'être relu depuis PostgreSQL, et
    ces empreintes sont celles de ce qui y est **effectivement** stocké. Si
    elles ne coïncidaient pas avec celles montrées au proposant, le dossier
    aurait changé entre les deux regards — que l'écran de B doit permettre de
    constater plutôt que de supposer.

    Passe par ``Digest``, dont le constructeur re-hache son payload : un
    ``hashlib.sha256`` écrit à la main ici serait une seconde façon de calculer
    la même chose, donc une seconde façon de se tromper.
    """
    def _e(payload: str) -> str:
        return Digest(
            algorithm="sha256",
            canonicalization_version=CANONICALIZATION_VERSION,
            canonical_payload=payload,
            digest=sha256(payload.encode("utf-8")).hexdigest(),
        ).digest

    return {
        "normative_spec_digest": _e(normative_spec_payload),
        "implementation_digest": _e(implementation_payload),
        "evidence_digest": _e(evidence_payload),
        "stack_digest": _e(stack_payload),
    }


@dataclass(frozen=True, slots=True)
class CitationDeRevue:
    """Le texte relevé dans le document publié, par une personne.

    ``document_digest`` désigne LEQUEL des documents requis cette citation
    couvre. Pour un paramètre national scalaire il n'y en a qu'un — l'annexe —
    mais le champ reste explicite : le jour où une règle s'appuie sur un
    corrigendum en plus du corps, une citation muette sur sa cible ne pourrait
    plus être rattachée.
    """

    document_digest: str
    quote: str
    page_printed: int
    page_pdf: int | None = None


@dataclass(frozen=True, slots=True)
class DossierCompose:
    """Les quatre payloads, leurs empreintes, et le résumé lisible.

    Les payloads sont ce qui part sur le fil et ce que PostgreSQL gèle. Les
    empreintes sont rendues **pour l'affichage** : le navigateur les montre à
    A puis à B, il ne les calcule pas et n'a aucun moyen de les fabriquer.
    """

    rule_id: str
    statement: str
    digest_algorithm: str
    canonicalization_version: str

    normative_spec: Digest
    implementation: Digest
    evidence: Digest
    stack: NormativeStack

    #: Ce qu'un ingénieur lit avant d'approuver, en clair.
    resume: dict[str, object]

    def payloads(self) -> dict[str, str]:
        """La forme exacte attendue par ``AuthorityReviewPackage``."""
        return {
            "rule_id": self.rule_id,
            "statement": self.statement,
            "digest_algorithm": self.digest_algorithm,
            "canonicalization_version": self.canonicalization_version,
            "normative_spec_payload": self.normative_spec.canonical_payload,
            "implementation_payload": self.implementation.canonical_payload,
            "evidence_payload": self.evidence.canonical_payload,
            "stack_payload": self.stack.digest.canonical_payload,
        }

    def empreintes(self) -> dict[str, str]:
        """Les quatre empreintes essentielles, pour l'écran de revue."""
        return {
            "normative_spec_digest": self.normative_spec.digest,
            "implementation_digest": self.implementation.digest,
            "evidence_digest": self.evidence.digest,
            "stack_digest": self.stack.digest.digest,
        }


def effet_normatif(parametre) -> str:
    """Ce que la clause citée FAIT, dérivé du registre et de lui seul.

    C'ÉTAIT UN CHAMP DU CLIENT, ET C'EST LE DÉFAUT QU'ON FERME. ``effect``
    entre dans ``normative_spec_payload``, donc dans l'empreinte de
    spécification : une phrase choisie par l'appelant déplaçait le sujet
    signé. Deux ingénieurs pouvaient relire la même clause et signer deux
    spécifications différentes parce qu'ils l'avaient décrite autrement.

    La phrase est maintenant une FONCTION du registre : mêmes champs, même
    texte, toujours. Elle reste lisible pour l'ingénieur qui relit, et elle ne
    peut plus être déplacée par personne.
    """
    return (
        f"fixe la valeur nationale de {parametre.parameter_name} "
        f"({parametre.national_annex_reference}, {parametre.clause})"
    )


def composer_dossier(
    parametre,
    *,
    statement: str,
    citations: tuple[CitationDeRevue, ...],
) -> DossierCompose:
    """Compose le dossier d'un paramètre national scalaire.

    ``parametre`` est une entrée du registre — la valeur, l'unité, la
    provenance, l'annexe, l'édition, la clause et l'empreinte du document en
    sortent, jamais de l'appelant.

    ``statement`` et ``citations`` sont la seule matière humaine, et elles ne
    portent que la PREUVE. Ni l'effet normatif ni l'empreinte
    d'implémentation ne s'en déduisent : le premier est une fonction du
    registre, la seconde une fonction du code déployé.

    Refuse, plutôt que de composer un dossier incomplet :

    * un paramètre sans empreinte de document déposée — aucune confirmation ne
      peut se rattacher à un document qu'on ne sait pas désigner ;
    * une règle dont le chemin de code n'est pas déclaré ;
    * une déclaration vide ;
    * une source requise sans citation, ou une citation qui ne correspond à
      aucune source requise. La couverture documentaire est vérifiée **ici**,
      pas reportée au moment où PostgreSQL rejettera le dossier.
    """
    if not getattr(parametre, "source_doc_id", None):
        raise ConfirmationDomainError(
            f"{parametre.key} n'a pas d'empreinte de document deposee: aucune "
            "confirmation ne peut y etre rattachee. Deposer d'abord le PDF de "
            "l'annexe et enregistrer son empreinte."
        )
    if not statement or not statement.strip():
        raise ConfirmationDomainError(
            "statement est vide. Le dossier de revue est ce que deux "
            "ingenieurs certifient avoir lu; un champ vide en ferait une "
            "formalite."
        )

    # L'EMPREINTE D'IMPLEMENTATION EST CALCULEE ICI, PAS RECUE.
    #
    # Elle est levee AVANT toute autre construction: une regle dont le chemin
    # de code n'est pas declare ne doit produire aucun dossier, pas un dossier
    # a qui il manquerait une empreinte.
    implementation = empreinte_implementation(parametre.key)
    effet = effet_normatif(parametre)

    spec = digest_of({
        "kind": "normative_spec",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "rule_id": parametre.key,
        "rule_type": "scalar",
        "output_unit": parametre.unit,
        "value_provenance": parametre.value_provenance.value,
        "scalar_value": parametre.parameter_value,
        "inputs": [],
        "domain": [],
        "expression_sources": [],
        "normative_authority": {
            "country_code": parametre.country_code,
            "reference": parametre.national_annex_reference,
            "edition": parametre.edition,
            "clause": parametre.clause,
            "effect": effet,
            "document_digest": parametre.source_doc_id,
        },
    })
    # LA COUVERTURE EST VERIFIEE AVANT DE HACHER QUOI QUE CE SOIT. Composer un
    # dossier auquel il manque une citation produirait une empreinte de preuve
    # parfaitement valide — et parfaitement fausse.
    par_document = {c.document_digest: c for c in citations}
    if len(par_document) != len(citations):
        raise ConfirmationDomainError(
            "deux citations designent le meme document. Une source, une "
            "citation: laquelle des deux aurait ete relue ?"
        )
    requises = required_sources(spec)
    manquantes = [s.document_digest for s in requises
                  if s.document_digest not in par_document]
    if manquantes:
        raise ConfirmationDomainError(
            "citation manquante pour " + ", ".join(sorted(manquantes)) +
            ". La specification declare ce document; sans le texte releve, "
            "rien n'atteste qu'il a ete ouvert."
        )
    attendues = {s.document_digest for s in requises}
    en_trop = sorted(d for d in par_document if d not in attendues)
    if en_trop:
        raise ConfirmationDomainError(
            "citation fournie pour " + ", ".join(en_trop) + ", que la "
            "specification ne declare pas. Un document en trop dans la preuve "
            "n'est pas neutre: il laisse croire a une couverture plus large."
        )

    items = tuple(
        EvidenceItem(
            document_digest=source.document_digest,
            document_role=source.role,
            reference=source.reference,
            edition=source.edition or parametre.edition,
            clause=source.clause,
            page_printed=par_document[source.document_digest].page_printed,
            quote=par_document[source.document_digest].quote,
            page_pdf=par_document[source.document_digest].page_pdf,
        )
        for source in requises
    )
    preuve = evidence_digest(items)

    pile = NormativeStack.of(
        country_code=parametre.country_code,
        standard_family=parametre.standard_family,
        part=parametre.part,
        components=(NormativeStackComponent(
            "annexe",
            parametre.national_annex_reference,
            parametre.edition,
            1,
            parametre.source_doc_id,
        ),),
    )

    return DossierCompose(
        rule_id=parametre.key,
        statement=statement,
        digest_algorithm="sha256",
        canonicalization_version=CANONICALIZATION_VERSION,
        normative_spec=spec,
        implementation=implementation,
        evidence=preuve,
        stack=pile,
        # LE RESUME EST UNE PROJECTION DES MEMES DONNEES, pas une seconde
        # source. Ce que l'ingenieur lit a l'ecran est ce qui a ete hache.
        resume={
            "rule_id": parametre.key,
            "country_code": parametre.country_code,
            "standard_family": parametre.standard_family,
            "part": parametre.part,
            "value": parametre.parameter_value,
            "unit": parametre.unit,
            "value_provenance": parametre.value_provenance.value,
            "validation_status": parametre.validation_status.value,
            "national_annex_reference": parametre.national_annex_reference,
            "edition": parametre.edition,
            "clause": parametre.clause,
            "source_doc_id": parametre.source_doc_id,
            "source_page": parametre.source_page,
            "usable_in_strict_mode": parametre.usable_in_strict_mode,
        },
    )
