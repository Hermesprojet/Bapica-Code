#!/usr/bin/env python3
"""Composer le dossier EXACT auquel une déclaration de validation se rapporte.

CE QU'UNE DÉCLARATION DOIT POUVOIR DÉSIGNER
--------------------------------------------
« Je valide les paramètres belges » ne désigne rien de vérifiable. Six mois
plus tard, personne ne peut dire quelles valeurs ont été validées, dans quelle
édition de l'annexe, sur quel exemplaire, ni contre quelle version du registre.

Ce script rend la liste, et il la rend **depuis le registre** — jamais depuis
une saisie. Pour chaque paramètre : la valeur ou ses branches, l'unité, la
clause, le folio, la référence de l'annexe, son édition, l'empreinte du
document lu, et la provenance du nombre. Plus une empreinte du dossier
lui-même, pour que deux lectures du même état donnent le même document.

CE QU'IL NE FAIT PAS, ET C'EST L'ESSENTIEL
--------------------------------------------
**Il ne confirme rien.** Il n'écrit pas dans `be.json`, ne touche à aucun
statut, et ne fabrique aucune identité. Une confirmation est l'acte daté de
deux ingénieurs nommés, enregistré par le chemin d'autorité dans une base —
proposition, approbation par un SECOND, consommation. Un script du dépôt ne
peut pas la produire, et celui-ci refuserait de le faire.

Ce qu'il produit est la pièce qu'on présente à ce chemin-là : la liste exacte
de ce sur quoi on s'apprête à signer.

Lancer depuis tools/ndp_import/ :
    python scripts/composer_dossier_de_validation.py --pays BE
    python scripts/composer_dossier_de_validation.py --pays BE --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]


def _registre(pays: str, calcul: str, as_of: date | None = None):
    sys.path.insert(0, str(REPO / "engine" / "src"))
    from eurostruct_engine.ec2.beam_verification import (
        required_parameters_for_beam,
    )
    from eurostruct_engine.ndp import load_parameter_set

    jeu = load_parameter_set(pays, strict=True, as_of=as_of)
    if calcul == "poutre":
        cles = required_parameters_for_beam(pays)
    else:
        cles = jeu.keys()
    return jeu, tuple(sorted(cles))


def _fiche(parametre) -> dict[str, Any]:
    """Ce qu'un ingénieur doit avoir sous les yeux pour signer CETTE valeur."""
    return {
        "key": parametre.key,
        "parameter_name": parametre.parameter_name,
        "description": parametre.description,
        "clause": parametre.clause,
        "unit": parametre.unit,
        "parameter_value": parametre.parameter_value,
        "variants": [
            {"condition": v.condition, "value": v.value,
             "description": v.description}
            for v in sorted(parametre.variants, key=lambda v: v.condition)
        ],
        "en_recommended": parametre.en_recommended,
        "national_annex_reference": parametre.national_annex_reference,
        "edition": parametre.edition,
        "effective_from": parametre.effective_from.isoformat(),
        "source_doc_id": parametre.source_doc_id,
        "source_page": parametre.source_page,
        "value_provenance": parametre.value_provenance.value,
        "validation_status": parametre.validation_status.value,
    }


def _version_du_registre(pays: str) -> dict[str, str]:
    """De QUEL état du registre ce dossier parle.

    L'empreinte du fichier de données, et celle du dossier rendu. Sans elles,
    une déclaration désigne « les paramètres belges » — c'est-à-dire ce qu'ils
    seront devenus le jour où on relira la déclaration.
    """
    fichier = REPO / f"engine/src/eurostruct_engine/ndp/data/{pays.lower()}.json"
    return {
        "fichier": str(fichier.relative_to(REPO)),
        "sha256": hashlib.sha256(fichier.read_bytes()).hexdigest(),
    }


def composer(pays: str, calcul: str,
             as_of: date | None = None) -> dict[str, Any]:
    jeu, cles = _registre(pays, calcul, as_of)
    fiches = []
    manquants = []
    for cle in cles:
        parametre = jeu.find(cle)
        if parametre is None:
            manquants.append(cle)
            continue
        fiches.append(_fiche(parametre))

    # CE QUI EST SIGNE. Rien d'autre n'entre dans l'empreinte -- voir plus bas.
    contenu: dict[str, Any] = {
        "pays": pays,
        "calcul": calcul,
        "registre": _version_du_registre(pays),
        "parametres": fiches,
        "absents": manquants,
        # CE QUE CE DOSSIER N'EST PAS. La phrase voyage avec le document: le
        # jour ou quelqu'un le retrouve sans son contexte, elle est dessus.
        "avertissement": (
            "Ce document LISTE ce sur quoi une validation porterait. Il ne "
            "confirme rien. Aucune valeur ci-dessous n'est opposable tant "
            "qu'elle n'a pas ete proposee, approuvee par un SECOND ingenieur "
            "nomme, et consommee par le chemin d'autorite."
        ),
    }
    # L'empreinte porte sur le CONTENU, jamais sur l'instant de la lecture.
    #
    # `as_of` etait dans le corps empreinte, et c'est la date du jour: le meme
    # registre, relu le lendemain, rendait une empreinte differente. Une
    # declaration qui cite « le dossier 0286... » aurait alors designe un
    # document que personne ne peut plus reproduire -- exactement le defaut que
    # l'empreinte existe pour empecher.
    #
    # L'exclure ne cache rien: `as_of` ne fait que SELECTIONNER les fiches
    # effectives. S'il change la selection, les fiches changent, et l'empreinte
    # change avec elles. S'il ne la change pas, deux lectures a six mois
    # d'intervalle rendent la meme empreinte -- ce qui est le fait a etablir.
    corps = json.dumps(contenu, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")).encode("utf-8")
    dossier = dict(contenu)
    dossier["dossier_sha256"] = hashlib.sha256(corps).hexdigest()
    # HORS EMPREINTE, ET DIT COMME TEL: la date de selection est un fait de
    # lecture, pas une clause du dossier.
    dossier["lu_avec_as_of"] = jeu.as_of.isoformat()
    return dossier


def _valeur_lisible(fiche: dict[str, Any]) -> str:
    if fiche["variants"]:
        return " ; ".join(f"{v['condition']} = {v['value']:g}"
                          for v in fiche["variants"])
    v = fiche["parameter_value"]
    return "—" if v is None else f"{v:g}"


def rendre(dossier: dict[str, Any]) -> str:
    lignes = [
        f"# Dossier de validation — {dossier['pays']} / {dossier['calcul']}",
        "",
        f"- Registre : `{dossier['registre']['fichier']}`",
        f"- Empreinte du registre : `{dossier['registre']['sha256']}`",
        f"- Empreinte de ce dossier : `{dossier['dossier_sha256']}`",
        (f"- Lu avec `as_of` = {dossier['lu_avec_as_of']} "
         "*(hors empreinte : date de sélection, pas clause du dossier)*"),
        f"- Paramètres : **{len(dossier['parametres'])}**",
        "",
        "Reproduire ce document, octet pour octet, depuis `tools/ndp_import/` :",
        "",
        "```",
        ("python scripts/composer_dossier_de_validation.py --pays "
         f"{dossier['pays']} --calcul {dossier['calcul']} "
         f"--as-of {dossier['lu_avec_as_of']}"),
        "```",
        "",
        f"> {dossier['avertissement']}",
        "",
        "| paramètre | valeur ou branches | unité | clause | annexe | folio |",
        "|---|---|---|---|---|---:|",
    ]
    for f in dossier["parametres"]:
        lignes.append(
            f"| `{f['parameter_name']}` | {_valeur_lisible(f)} | "
            f"{f['unit']} | {f['clause']} | {f['national_annex_reference']} | "
            f"{f['source_page'] if f['source_page'] is not None else '—'} |"
        )

    editions = sorted({f["edition"] for f in dossier["parametres"]})
    documents = sorted({f["source_doc_id"] for f in dossier["parametres"]
                        if f["source_doc_id"]})
    provenances = sorted({f["value_provenance"] for f in dossier["parametres"]})
    statuts = sorted({f["validation_status"] for f in dossier["parametres"]})

    lignes += [
        "",
        "## Sources",
        "",
        "Éditions citées : " + ", ".join(f"`{e}`" for e in editions),
        "",
        "Documents lus (SHA-256) :",
        "",
    ]
    lignes += [f"- `{d}`" for d in documents]
    lignes += [
        "",
        "Provenance des valeurs : " + ", ".join(f"`{p}`" for p in provenances),
        "",
        "Statut dans le dépôt : " + ", ".join(f"`{s}`" for s in statuts),
        "",
    ]
    if dossier["absents"]:
        lignes += ["", "**Paramètres demandés et absents du registre :**", ""]
        lignes += [f"- `{k}`" for k in dossier["absents"]]
    return "\n".join(lignes) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pays", required=True)
    ap.add_argument("--calcul", default="poutre",
                    choices=("poutre", "tous"),
                    help="« poutre »: les parametres que les cinq chapitres "
                         "reclament. « tous »: le registre entier du pays.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--as-of", dest="as_of", default=None,
                    help="AAAA-MM-JJ. Date de SELECTION des fiches effectives. "
                         "Elle n'entre pas dans l'empreinte du dossier: deux "
                         "dates qui selectionnent les memes fiches rendent la "
                         "meme empreinte.")
    args = ap.parse_args(argv[1:])

    dossier = composer(args.pays.upper(), args.calcul,
                       date.fromisoformat(args.as_of) if args.as_of else None)
    if args.json:
        print(json.dumps(dossier, indent=2, ensure_ascii=False))
    else:
        print(rendre(dossier), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
