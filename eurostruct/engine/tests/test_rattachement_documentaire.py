"""Ce a quoi une fiche nationale rattache sa valeur: un fichier, une page.

CE QUE CE FICHIER DEFEND
-------------------------
`source_doc_id` est le seul lien entre un nombre du registre et le document
d'ou il sort. `passerelle._ecart_de_sujet` exige que le dossier signe cite la
MEME empreinte, et `dossier.composer_dossier` refuse de composer sans elle.
Si cette valeur n'est pas l'empreinte d'un fichier, le lien a la forme d'une
preuve et n'en est pas une.

Elle ne l'etait pas. Vingt-deux parametres belges portaient 48 caracteres
hexadecimaux — les 192 premiers bits d'un SHA-256, tronques par une constante
de generateur dont le commentaire affirmait le contraire. Aucun depot n'aurait
pu rendre cette valeur.

Les cas ci-dessous mesurent la forme, pas la valeur: ils ne peuvent pas ouvrir
le PDF, qui est un document NBN payant et n'est pas versionne. Ce qu'ils
peuvent faire, et font, c'est refuser une empreinte qui n'a pas la forme d'un
SHA-256, et verifier que les deux references du depot concordent avec ce que
le registre porte.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from eurostruct_engine.ndp import load_country_registry
from eurostruct_engine.ndp.model import ValidationStatus

RACINE = Path(__file__).resolve().parents[2]
CATALOGUE = RACINE / "tools/ndp_import/src/ndp_import/data/catalogue.json"
DOSSIER_BE = RACINE / "docs/relecture/dossier_be_EN199211.md"

PAYS = ("BE", "FR", "DE", "ES")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

#: L'exemplaire depouille par le pipeline d'import.
ANB_TEXTE = "7951964092a4ad595f4d7ea95bea7e2099ca75d83c669a05561ecafb386b37a1"
#: L'exemplaire sur lequel le Tableau 7.1N-ANB est lisible.
ANB_LISIBLE = "3a19536221aef69b16435b88bc05d7aee05cebe823e98cb292e49e48fe68dcdd"


def _parametres(pays: str):
    return [p for a in load_country_registry(pays).annexes for p in a.parameters]


@pytest.mark.parametrize("pays", PAYS)
def test_toute_empreinte_portee_a_la_forme_d_un_sha256(pays: str) -> None:
    """Quarante-huit caracteres ne sont pas une empreinte.

    C'EST LE CAS QUI MANQUAIT. Rien ne regardait la forme de ce champ, si
    bien qu'une troncature y a vecu des mois en ressemblant a une empreinte.
    Une chaine hexadecimale ressemble toujours a une empreinte; seule sa
    LONGUEUR dit si c'en est une.
    """
    fautifs = [
        (p.parameter_name, p.source_doc_id)
        for p in _parametres(pays)
        if p.source_doc_id is not None and not _SHA256.match(p.source_doc_id)
    ]
    assert fautifs == [], (
        f"{pays}: empreinte(s) qui ne sont pas un SHA-256 en 64 caracteres "
        f"minuscules: {fautifs}"
    )


def test_les_fiches_belges_citent_l_exemplaire_de_leur_lecture() -> None:
    """Deux exemplaires de la meme edition, et ils ne se confondent pas.

    Le Tableau 7.1N-ANB n'est lisible que sur le second. Les rassembler sous
    une seule empreinte effacerait precisement ce fait, et rendrait
    incontrolable la question « sur quel rendu cette valeur a-t-elle ete
    lue ? ».
    """
    par_nom = {p.parameter_name: p for p in _parametres("BE")}

    assert par_nom["w_max"].source_doc_id == ANB_LISIBLE
    assert par_nom["alpha_cc"].source_doc_id == ANB_TEXTE

    portees = {p.source_doc_id for p in par_nom.values() if p.source_doc_id}
    assert portees == {ANB_TEXTE, ANB_LISIBLE}


def test_les_fiches_obsoletes_ne_citent_aucun_document() -> None:
    """Six fiches n'ont plus de lecture, et leur champ le dit.

    `alpha_cw`, `nu1_coeff`, `nu1_fck_divisor`, `rho_w_min_coeff`,
    `s_l_max_coeff` et `s_t_max_coeff` sont remplacees par les regles typees
    de `ndp/rules_be_ec2.py`. Leur rendre une empreinte les ferait passer
    pour des valeurs relevees.
    """
    sans = sorted(
        p.parameter_name for p in _parametres("BE") if p.source_doc_id is None
    )
    assert sans == [
        "alpha_cw", "nu1_coeff", "nu1_fck_divisor", "rho_w_min_coeff",
        "s_l_max_coeff", "s_t_max_coeff",
    ]
    for p in _parametres("BE"):
        if p.source_doc_id is None:
            assert p.validation_status is ValidationStatus.DEPRECATED, (
                f"{p.parameter_name} n'a pas d'empreinte sans etre obsolete"
            )


def test_l_empreinte_restauree_concorde_avec_les_deux_references_du_depot(
) -> None:
    """LA RESTAURATION EST VERIFIABLE SANS LE FICHIER, et voici comment.

    Le PDF n'est pas versionne. Ce qui l'est, ce sont deux enregistrements
    independants de son empreinte — le catalogue d'acquisition et le dossier
    de relecture produit le 27/07. Ils doivent dire la meme chose, et le
    registre doit dire cela.
    """
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    entree = next(d for d in catalogue["documents"]
                  if d.get("doc_key") == "BE-EN199211-NA")

    depuis_dossier = None
    for ligne in DOSSIER_BE.read_text(encoding="utf-8").splitlines():
        if "Empreinte SHA-256" in ligne:
            trouve = re.search(r"\b([0-9a-f]{64})\b", ligne)
            if trouve:
                depuis_dossier = trouve.group(1)
                break

    assert entree["doc_id_sha256"] == ANB_TEXTE
    assert depuis_dossier == ANB_TEXTE

    # Et le second exemplaire est catalogue comme tel, pas ignore: sans cela,
    # `w_max` citerait un document que le catalogue ne connait pas.
    assert ANB_LISIBLE in (entree.get("alternate_copy_hashes") or [])


def test_une_attestation_prise_sur_l_ancienne_empreinte_n_ouvre_plus_rien(
) -> None:
    """LES ATTESTATIONS NE SUIVENT PAS UN CONTENU QUI A CHANGE.

    C'est la garantie qui rendait la correction possible sans reprendre les
    signatures: une confirmation porte sur un dossier, ce dossier cite une
    empreinte de document, et la passerelle compare cette empreinte a celle
    du registre. Une attestation prise sur les 48 caracteres reste dans
    l'historique — elle a eu lieu — et ne confirme plus rien.

    Le cas le mesure en composant un dossier sur l'ANCIENNE empreinte, puis
    en le presentant a la passerelle contre le registre d'aujourd'hui.
    """
    import dataclasses
    from datetime import UTC, datetime

    from eurostruct_engine.ndp.canonical import EvidenceItem
    from eurostruct_engine.ndp.confirmation import (
        NormativeReviewPackage,
        NormativeRuleConfirmation,
        required_sources,
    )
    from eurostruct_engine.ndp.dossier import CitationDeRevue, composer_dossier
    from eurostruct_engine.ndp.passerelle import evaluer_depuis_le_provider
    from eurostruct_engine.ndp.registry import load_parameter_set

    TRONQUEE = "7951964092a4ad595f4d7ea95bea7e2099ca75d83c669a05"

    jeu = load_parameter_set("BE", strict=True)
    vrai = jeu.find("EN 1992-1-1:alpha_cc")
    perime = dataclasses.replace(vrai, source_doc_id=TRONQUEE)

    compose = composer_dossier(
        perime,
        statement="FICTIF — dossier compose sur l'ancienne empreinte.",
        citations=(CitationDeRevue(
            document_digest=TRONQUEE,
            quote="FICTIF — citation relevee.",
            page_printed=perime.source_page or 1,
        ),),
    )
    paquet = NormativeReviewPackage.of(
        country_code=perime.country_code,
        standard_family=perime.standard_family,
        part=perime.part,
        rule_id=perime.key,
        stack=compose.stack,
        normative_spec=compose.normative_spec,
        implementation=compose.implementation,
        evidence_items=tuple(
            EvidenceItem(
                document_digest=s.document_digest, document_role=s.role,
                reference=s.reference, edition=s.edition or perime.edition,
                clause=s.clause, page_printed=perime.source_page or 1,
                quote="FICTIF — citation relevee.", page_pdf=None,
            )
            for s in required_sources(compose.normative_spec)
        ),
    )

    class Fournisseur:
        provider_identity = "FICTIF://empreinte-perimee"
        is_fictional = True

        def confirmations_for(self, rule_id: str):
            return tuple(
                NormativeRuleConfirmation.for_package(
                    paquet,
                    confirmation_id=f"FICTIF-conf-{qui}",
                    verifier_id=f"FICTIF-{qui}",
                    verifier_name=f"FICTIF {qui.title()}",
                    verified_at=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
                    authorisations_at_signature=frozenset(
                        {"can_validate_normative_reference"}),
                    authorisation_scope_at_signature="BE/EN 1992/1-1",
                    statement="FICTIF — relu a la page citee.",
                    idempotency_key=f"FICTIF-idem-{qui}",
                )
                for qui in ("alice", "bob")
            )

        def revocations_for(self, rule_id: str):
            return ()

    rapport = evaluer_depuis_le_provider(vrai, provider=Fournisseur())
    assert not rapport.usable
    assert "document" in rapport.reason, rapport.reason
    # Le refus NOMME les deux empreintes: sans cela, l'ingenieur ne sait pas
    # que c'est le document qui a bouge et non sa signature.
    assert ANB_TEXTE[:16] in rapport.reason
    assert TRONQUEE[:16] in rapport.reason
