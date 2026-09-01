#!/usr/bin/env python3
"""Generate the TypeScript contract from the Pydantic models.

The frontend must never hand-write the shapes it exchanges with the engine: a
field renamed on one side and not the other is exactly the class of bug that
ends up producing a wrong number in a note de calcul. This script is the single
source of truth in the other direction — Pydantic models in, TypeScript out.

Run it from ``engine/``::

    python scripts/export_contracts.py

and commit the result. CI re-runs it and fails if the checked-in file differs,
so the two sides cannot drift.

The emitter is deliberately small and deterministic (sorted keys everywhere)
rather than pulling in a code generator: the subset of JSON Schema that
Pydantic produces for these models is narrow and fully covered here.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
ENGINE = REPO / "engine"
sys.path.insert(0, str(ENGINE / "src"))

from eurostruct_engine.schemas.autorite import (  # noqa: E402
    AuthorityDecisionConsumed,
    AuthorityDecisionCreated,
    AuthorityDecisionRequest,
    AuthorityDecisionReview,
    AuthorityReviewDossier,
    AuthorityReviewDraftRequest,
)
from eurostruct_engine.schemas.atelier import (  # noqa: E402
    AttestationDemande,
    CalculDeProjetRequest,
    CalculEnregistre,
    HistoriqueCalculs,
    ListeLivrables,
    ListeProjets,
    Livrable,
    LivrableCreation,
    LivrableDetail,
    Projet,
    ProjetCreation,
    RetourAuBrouillon,
    Transition,
)
from eurostruct_engine.schemas.organisation import (  # noqa: E402
    AdhesionModifiee,
    Invitation,
    InvitationAcceptee,
    InvitationCreation,
    InvitationEmise,
    JetonInvitation,
    ListeInvitations,
    ListeMembres,
    Membre,
    MembreModification,
    Organisation,
    OrganisationCreation,
)
from eurostruct_engine.schemas.common import (  # noqa: E402
    EngineErrorDTO,
    NdpSummaryDTO,
    PreflightReportDTO,
)
from eurostruct_engine.schemas.ec2_beam import (  # noqa: E402
    BeamSectionDrawingRequest,
    Ec2BeamFlexureRequest,
    Ec2BeamFlexureResponse,
    Ec2BeamSectionRequest,
    RebarScheduleRowDTO,
)
from eurostruct_engine.schemas.ec2_verification import (  # noqa: E402
    Ec2BeamVerificationRequest,
    Ec2BeamVerificationResponse,
)

#: Root models. Their transitive dependencies are emitted automatically.
ROOTS = [
    Ec2BeamFlexureRequest,
    Ec2BeamFlexureResponse,
    # LA VERIFICATION COMPLETE — CINQ CHAPITRES, UNE SEULE SAISIE.
    #
    # C'est la forme la plus dangereuse a recopier a la main, pour deux
    # raisons opposees. Ce qu'elle PORTE d'abord: dix-sept entrees dont
    # `phi_creep`, `structural_system` ou `anchorage_available`, qu'aucune
    # geometrie ne revele et qu'un ecran ne peut pas deviner.
    #
    # Ce qu'elle N'A PAS ensuite, et c'est le plus important: ni `status`, ni
    # `may_be_finalised`, ni empreinte, ni `A_s`, ni pays. Un ecran qui
    # recopierait la forme finirait par ajouter l'un de ces champs « pour
    # afficher », et le jour ou il le POSTE, un client deciderait de sa propre
    # conformite. Le type genere le lui interdit a la compilation.
    Ec2BeamVerificationRequest,
    Ec2BeamVerificationResponse,
    # La requete que l'interface envoie: elle porte le calcul ET le
    # ferraillage choisi, si bien que le dessin ne peut pas decrire une autre
    # section que celle qui vient d'etre verifiee.
    Ec2BeamSectionRequest,
    BeamSectionDrawingRequest,
    RebarScheduleRowDTO,
    NdpSummaryDTO,
    PreflightReportDTO,
    EngineErrorDTO,
    # Le chemin d'autorite. Sans ces trois-la, tout client devait RECOPIER la
    # forme en TypeScript — et une forme recopiee derive le jour ou un champ
    # est renomme. Ici le champ en question decide qui peut confirmer une
    # valeur nationale.
    AuthorityDecisionRequest,
    AuthorityDecisionCreated,
    AuthorityDecisionConsumed,
    # LA COMPOSITION DU DOSSIER ET SA RELECTURE. Le navigateur ne construit
    # aucune empreinte normative: il demande au serveur de composer, affiche
    # ce qu'il rend, et relit depuis la base ce que le second regard doit
    # juger. Sans ces formes generees, cet ecran-la aurait ete le seul a
    # recopier ses types a la main.
    AuthorityReviewDraftRequest,
    AuthorityReviewDossier,
    AuthorityDecisionReview,
    # L'ATELIER. Le navigateur cree un projet, le selectionne, lance un calcul
    # et rouvre l'historique: cinq formes, dont deux qu'il POSTE. Recopiees a
    # la main, elles auraient derive au premier champ renomme — et le champ en
    # question decide dans quelle organisation un projet est cree.
    ListeProjets,
    Projet,
    ProjetCreation,
    # LE CALCUL DE PROJET NE NOMME AUCUN REFERENTIEL. Le type genere est ce
    # qui l'impose au navigateur: pays, region et date n'y figurent pas, donc
    # l'ecran ne peut pas les envoyer meme par erreur.
    CalculDeProjetRequest,
    HistoriqueCalculs,
    CalculEnregistre,
    # LES LIVRABLES ET LEUR PARCOURS DE RELECTURE. L'ecran affiche un etat,
    # propose des actions, et POSTE trois corps: creer un brouillon, renvoyer
    # au brouillon avec un motif, attester. Les trois sont volontairement
    # minces — un identifiant de calcul, un motif, un texte — et c'est
    # exactement ce que le type genere impose au navigateur: aucun champ pour
    # nommer une organisation, un validateur, une empreinte ou un etat.
    LivrableCreation,
    RetourAuBrouillon,
    AttestationDemande,
    Transition,
    Livrable,
    LivrableDetail,
    ListeLivrables,
    # L'ENTREE DANS L'APPLICATION. L'ecran d'un compte tout neuf n'a rien a
    # afficher et tout a proposer: fonder son bureau, ou rejoindre celui de
    # quelqu'un avec un lien. Les douze formes descendent du meme contrat que
    # le reste — et l'une d'elles porte, une seule fois, le secret d'une
    # invitation, ce qui est exactement la raison de ne pas la recopier a la
    # main quelque part.
    OrganisationCreation,
    Organisation,
    InvitationCreation,
    InvitationEmise,
    JetonInvitation,
    InvitationAcceptee,
    Invitation,
    ListeInvitations,
    Membre,
    ListeMembres,
    MembreModification,
    AdhesionModifiee,
]

TS_OUT = REPO / "packages" / "contracts" / "src" / "generated" / "engine.ts"
JSON_OUT = REPO / "packages" / "contracts" / "schema" / "engine.schema.json"

HEADER = """\
/**
 * GENERATED FILE — DO NOT EDIT.
 *
 * Produced by engine/scripts/export_contracts.py from the Pydantic models in
 * engine/src/eurostruct_engine/schemas/. Edit those, then re-run:
 *
 *     cd engine && python scripts/export_contracts.py
 *
 * CI fails if this file is out of date with the models.
 *
 * Every physical value crosses the wire as a QuantityDTO carrying its unit.
 * There are no bare numbers for dimensional quantities, by design.
 */

/* eslint-disable */
"""


def ts_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def to_ts(schema: dict[str, Any], indent: int = 0) -> str:
    """Convert one JSON Schema node to a TypeScript type expression."""
    if "$ref" in schema:
        return ts_name(schema["$ref"])

    if "const" in schema:
        return json.dumps(schema["const"])

    if "enum" in schema:
        return " | ".join(json.dumps(v) for v in schema["enum"])

    for key in ("anyOf", "oneOf"):
        if key in schema:
            parts = [to_ts(s, indent) for s in schema[key]]
            # Collapse the common `T | null` produced by `X | None`.
            seen: list[str] = []
            for p in parts:
                if p not in seen:
                    seen.append(p)
            return " | ".join(seen)

    t = schema.get("type")

    if t == "array":
        if "prefixItems" in schema:  # fixed-length tuple
            return "[" + ", ".join(to_ts(s, indent) for s in schema["prefixItems"]) + "]"
        items = schema.get("items")
        inner = to_ts(items, indent) if items else "unknown"
        return f"({inner})[]" if " " in inner else f"{inner}[]"

    if t == "object" or "properties" in schema:
        if "properties" in schema:
            return emit_object(schema, indent)
        extra = schema.get("additionalProperties")
        inner = to_ts(extra, indent) if isinstance(extra, dict) else "unknown"
        return f"Record<string, {inner}>"

    return {
        "string": "string",
        "number": "number",
        "integer": "number",
        "boolean": "boolean",
        "null": "null",
    }.get(t, "unknown")


def emit_object(schema: dict[str, Any], indent: int) -> str:
    pad = "  " * (indent + 1)
    required = set(schema.get("required", []))
    lines = ["{"]
    for name in sorted(schema.get("properties", {})):
        prop = schema["properties"][name]
        doc = prop.get("description")
        if doc:
            lines.append(f"{pad}/** {' '.join(doc.split())} */")
        optional = "" if name in required else "?"
        lines.append(f"{pad}{name}{optional}: {to_ts(prop, indent + 1)};")
    lines.append("  " * indent + "}")
    return "\n".join(lines)


def emit_named(name: str, schema: dict[str, Any]) -> str:
    doc = schema.get("description")
    header = f"/** {' '.join(doc.split())} */\n" if doc else ""
    if "enum" in schema and "properties" not in schema:
        return f"{header}export type {name} =\n  | " + "\n  | ".join(
            json.dumps(v) for v in schema["enum"]
        ) + ";"
    return f"{header}export interface {name} {emit_object(schema, 0)}"


def main() -> int:
    defs: dict[str, Any] = {}
    roots: dict[str, Any] = {}

    for model in ROOTS:
        schema = model.model_json_schema(ref_template="#/$defs/{model}")
        defs.update(schema.pop("$defs", {}))
        roots[model.__name__] = schema

    # Root models may also appear as a dependency of another root.
    for name, schema in roots.items():
        defs.setdefault(name, schema)

    blocks = [emit_named(name, defs[name]) for name in sorted(defs)]
    ts = HEADER + "\n" + "\n\n".join(blocks) + "\n"

    TS_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    TS_OUT.write_text(ts, encoding="utf-8")
    JSON_OUT.write_text(
        json.dumps({"$defs": defs}, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"wrote {TS_OUT.relative_to(REPO)}  ({len(defs)} types)")
    print(f"wrote {JSON_OUT.relative_to(REPO)}")

    if "--check" in sys.argv:
        diff = subprocess.run(
            ["git", "diff", "--exit-code", "--", str(TS_OUT), str(JSON_OUT)],
            cwd=REPO,
        )
        if diff.returncode != 0:
            print(
                "\nLe contrat TypeScript n'est pas a jour avec les modeles "
                "Pydantic. Executer: cd engine && python scripts/export_contracts.py",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
