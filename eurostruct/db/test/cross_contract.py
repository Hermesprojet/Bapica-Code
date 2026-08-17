#!/usr/bin/env python3
"""EUROSTRUCT — 6.3b3: contrat croise Python <-> PostgreSQL.

POURQUOI CE FICHIER EXISTE
---------------------------
Les payloads canoniques des garanties SQL sont ecrits A LA MAIN dans
``05_normative_confirmation.sql``. Ils *ressemblent* a ce que produit
``eurostruct_engine.ndp.canonical``, et c'est precisement le probleme : une
fixture ecrite a la main ne peut pas etre l'unique definition du contrat. Le
jour ou la canonicalisation changera d'un caractere — une cle renommee, un
separateur, une normalisation Unicode — les fixtures continueront de passer et
la base acceptera un format que le moteur ne produit plus.

Ce script ferme la boucle dans les deux sens :

    Python produit un VRAI paquet de revue
      -> PostgreSQL l'accepte, applique ses declencheurs, derive ses colonnes
      -> Python relit ce que PostgreSQL a stocke
      -> Python RECONSTRUIT les objets du domaine et exige l'identite

Aucun octet n'est retape entre les deux extremites.

POURQUOI PAS UN TEST PYTEST
----------------------------
``test_confirmation_domain`` verifie que le moteur n'importe AUCUN pilote de
base (``psycopg``, ``sqlalchemy``, ``asyncpg``, ``sqlite3``). Cette isolation
est une garantie du projet, pas une commodite : le moteur de calcul ne parle
pas a une base. Le transport est donc ``psql`` lui-meme, pilote par
``cross_contract.sh`` — et ce script reste du Python pur.

AUCUNE CONFIRMATION REELLE
---------------------------
La regle utilisee est une vraie regle du referentiel belge, mais rien n'est
confirme : un paquet de revue est ce qu'on PRESENTERAIT a un relecteur. Le
verificateur, l'octroi et la declaration sont fictifs et portent « FICTIF ».

Usage:
    cross_contract.py emit   > paquet.json
    cross_contract.py verify paquet.json relu.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2] / "engine" / "src"
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from eurostruct_engine.ndp import rules_be_ec2 as reelles  # noqa: E402
from eurostruct_engine.ndp.canonical import (  # noqa: E402
    Digest,
    EvidenceItem,
    evidence_digest,
    implementation_digest,
    normative_spec_digest,
)
from eurostruct_engine.ndp.confirmation import (  # noqa: E402
    NormativeReviewPackage,
    NormativeStack,
    NormativeStackComponent,
    required_sources,
)

REGLE = reelles.RHO_W_MIN
PAYS, FAMILLE, PARTIE = "BE", "EN 1992", "1-1"


# ---------------------------------------------------------------------------
# Construction d'un paquet REEL
# ---------------------------------------------------------------------------
def paquet_reel() -> NormativeReviewPackage:
    """Un paquet de revue complet pour une vraie regle du referentiel belge.

    Une preuve PAR SOURCE, et non par document : ``be.ec2.rho_w_min`` declare
    quatre sources reparties sur trois documents — le corps de l'EN et le
    corrigendum AC:2008 sont relies dans le meme PDF belge et partagent leur
    empreinte. Un dossier construit par document serait refuse, et c'est voulu.
    """
    spec = normative_spec_digest(REGLE)
    impl = implementation_digest(REGLE)
    sources = required_sources(spec)

    items = tuple(
        EvidenceItem(
            document_digest=s.document_digest,
            document_role=s.role,
            reference=s.reference,
            edition=s.edition or "2010",
            clause=s.clause,
            page_printed=100 + i,
            # Accent compose et tiret cadratin: si un maillon de la chaine
            # reencodait ou renormalisait le texte, le quote_digest ne
            # correspondrait plus et PostgreSQL refuserait la ligne.
            quote=f"FICTIF — citation de contrôle n°{i + 1}, clause {s.clause}.",
        )
        for i, s in enumerate(sources)
    )

    pile = NormativeStack.of(
        country_code=PAYS, standard_family=FAMILLE, part=PARTIE,
        components=tuple(
            NormativeStackComponent(
                s.role, s.reference, s.edition or "2010", i + 1,
                s.document_digest,
            )
            for i, s in enumerate(sources)
        ),
    )

    return NormativeReviewPackage.of(
        country_code=PAYS, standard_family=FAMILLE, part=PARTIE,
        rule_id=REGLE.rule_id, stack=pile,
        normative_spec=spec, implementation=impl, evidence_items=items,
    )


def emettre() -> dict:
    """Le paquet, sous la forme que ``cross_contract.sh`` passera a psql."""
    p = paquet_reel()
    ev = evidence_digest(p.evidence_items)
    if ev != p.evidence:
        raise SystemExit(
            "l'empreinte de preuve recalculee differe de celle du paquet: le "
            "paquet emis ne serait pas celui qu'on croit"
        )

    # `annex_edition` que le SERVEUR devra deriver lui-meme de la pile. On ne
    # l'envoie pas: on l'attend en retour, et on le compare.
    annexes = [c for c in p.stack.components if c.role == "annexe"]
    return {
        "country_code": p.country_code,
        "standard_family": p.standard_family,
        "part": p.part,
        "rule_id": p.rule_id,
        "digest_algorithm": p.normative_spec.algorithm,
        "canonicalization_version": p.normative_spec.canonicalization_version,
        "stack_digest": p.stack.digest.digest,
        "normative_spec_digest": p.normative_spec.digest,
        "implementation_digest": p.implementation.digest,
        "evidence_digest": p.evidence.digest,
        "stack_payload": p.stack.digest.canonical_payload,
        "normative_spec_payload": p.normative_spec.canonical_payload,
        "implementation_payload": p.implementation.canonical_payload,
        "evidence_payload": p.evidence.canonical_payload,
        # Attendus, jamais envoyes: c'est le SERVEUR qui doit les deriver, et
        # on compare ensuite. L'edition retenue est celle du composant
        # « annexe » d'ordre d'application le plus eleve — la meme regle que
        # le declencheur, ecrite ici independamment.
        "attendu_annex_edition": annexes[-1].edition if annexes else None,
        "attendu_nb_items": len(p.evidence_items),
    }


# ---------------------------------------------------------------------------
# Verification du retour
# ---------------------------------------------------------------------------
class Divergence(SystemExit):
    def __init__(self, message: str) -> None:
        super().__init__(f"DIVERGENCE — {message}")


def _egal(quoi: str, envoye, relu) -> None:
    if envoye != relu:
        raise Divergence(
            f"{quoi}: envoye {envoye!r}, relu {relu!r}. Le contrat entre le "
            "moteur et la base n'est pas tenu."
        )


def verifier(emis: dict, relu: dict) -> list[str]:
    """Reconstruire depuis PostgreSQL, et exiger l'identite."""
    controles: list[str] = []

    # --- 1. Les payloads sont rendus OCTET POUR OCTET ----------------------
    # La colonne est `text` et non `jsonb`, et ce test est ce qui l'impose :
    # `jsonb` reordonnerait les cles et normaliserait les espaces, l'empreinte
    # ne correspondrait plus a rien, et le paquet deviendrait illisible dix ans
    # plus tard — exactement ce que la conservation du payload existe pour
    # eviter.
    for champ in ("stack_payload", "normative_spec_payload",
                  "implementation_payload", "evidence_payload"):
        _egal(champ, emis[champ], relu[champ])
    controles.append("payloads canoniques rendus octet pour octet")

    # --- 2. Les Digest se reconstruisent depuis ce que la base a stocke ----
    # `Digest.__post_init__` recalcule sha256(payload) et refuse un hash qui ne
    # correspond pas. Reconstruire ici, c'est donc verifier l'integrite du
    # couple (payload, empreinte) TEL QU'IL SORT DE POSTGRESQL, sans lui faire
    # confiance.
    paires = {
        "normative_spec": ("normative_spec_payload", "normative_spec_digest"),
        "implementation": ("implementation_payload", "implementation_digest"),
        "evidence": ("evidence_payload", "evidence_digest"),
        "stack": ("stack_payload", "stack_digest"),
    }
    reconstruits: dict[str, Digest] = {}
    for nom, (cle_payload, cle_digest) in paires.items():
        try:
            reconstruits[nom] = Digest(
                algorithm=relu["digest_algorithm"],
                canonicalization_version=relu["canonicalization_version"],
                canonical_payload=relu[cle_payload],
                digest=relu[cle_digest],
            )
        except Exception as exc:                       # noqa: BLE001
            raise Divergence(
                f"{nom}: impossible de reconstruire l'empreinte depuis la "
                f"base ({exc})"
            ) from exc
        _egal(f"{nom} digest", emis[cle_digest], reconstruits[nom].digest)
    controles.append("quatre Digest reconstruits et verifies depuis la base")

    # --- 3. Les projections DERIVEES par le serveur ------------------------
    # Ce que Python n'a pas envoye et que le serveur a calcule seul.
    pile_relue = relu["stack_snapshot"]
    if pile_relue != json.loads(emis["stack_payload"]):
        raise Divergence(
            "stack_snapshot ne correspond pas au stack_payload signe: la pile "
            "stockee n'est pas celle qui est hachee"
        )
    items_relus = relu["evidence_items"]
    _egal("nombre d'elements de preuve", emis["attendu_nb_items"],
          len(items_relus))
    _egal("annex_edition derivee par le serveur",
          emis["attendu_annex_edition"], relu["annex_edition"])
    controles.append("projections derivees par le serveur conformes")

    # --- 4. Le paquet se RECONSTRUIT, et sa cle de sujet est la meme -------
    # Le controle qui donne son sens aux trois precedents : on ne compare pas
    # des chaines, on refabrique les objets du domaine depuis ce que la base a
    # rendu et on exige que le sujet confirme soit identique. Toute divergence
    # de structure — un champ perdu, un ordre change, une edition mal derivee —
    # deplace le subject_key.
    pile = NormativeStack(
        schema_version=pile_relue["schema_version"],
        country_code=pile_relue["country_code"],
        standard_family=pile_relue["standard_family"],
        part=pile_relue["part"],
        components=tuple(
            NormativeStackComponent(
                c["role"], c["reference"], c["edition"],
                c["application_order"], c["document_digest"],
            )
            for c in sorted(pile_relue["components"],
                            key=lambda c: c["application_order"])
        ),
    )
    _egal("empreinte de la pile reconstruite",
          emis["stack_digest"], pile.digest.digest)

    items = tuple(
        EvidenceItem(
            document_digest=i["document_digest"],
            document_role=i["document_role"],
            reference=i["reference"],
            edition=i["edition"],
            clause=i["clause"],
            page_printed=int(i["page_printed"]),
            quote=i["quote"],
        )
        for i in items_relus
    )
    _egal("empreinte de preuve reconstruite",
          emis["evidence_digest"], evidence_digest(items).digest)

    refait = NormativeReviewPackage.of(
        country_code=relu["country_code"],
        standard_family=relu["standard_family"],
        part=relu["part"],
        rule_id=relu["rule_id"],
        stack=pile,
        normative_spec=reconstruits["normative_spec"],
        implementation=reconstruits["implementation"],
        evidence_items=items,
    )
    origine = paquet_reel()
    if refait.subject_key != origine.subject_key:
        raise Divergence(
            "le paquet reconstruit depuis PostgreSQL n'a pas le meme "
            f"subject_key:\n  origine  {origine.subject_key}\n"
            f"  relu     {refait.subject_key}"
        )
    controles.append("paquet reconstruit: subject_key identique a l'origine")

    # --- 5. Le sujet stocke en COLONNES est celui du paquet ----------------
    # Les colonnes servent a la recherche; les payloads a la preuve. Si les
    # deux divergeaient, on chercherait une regle et on en signerait une autre.
    for champ in ("country_code", "standard_family", "part", "rule_id"):
        _egal(f"colonne {champ}", emis[champ], relu[champ])
    controles.append("colonnes de recherche conformes au sujet signe")

    return controles


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "emit":
        json.dump(emettre(), sys.stdout, ensure_ascii=False,
                  separators=(",", ":"))
        return 0

    if len(sys.argv) == 4 and sys.argv[1] == "verify":
        emis = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        relu = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
        for c in verifier(emis, relu):
            print(f"      ok: {c}")
        return 0

    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
