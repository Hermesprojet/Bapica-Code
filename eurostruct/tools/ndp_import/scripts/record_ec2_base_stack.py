#!/usr/bin/env python3
"""Enregistrer la pile normative EC2 belge: base, corrigenda, amendement.

Pourquoi ce script existe
--------------------------
Le catalogue comptait ZERO Eurocode de base, pour quatre pays, alors que des
normes de base etaient sur le disque depuis des semaines. Elles avaient ete
triees, correctement refusees comme sources de NDP — une norme de base ne
porte que des valeurs recommandees — puis oubliees.

L'erreur de raisonnement etait la: « ne peut pas confirmer un NDP » avait ete
traite comme « sans interet ». Or les Annexes Nationales fonctionnent par
DESIGNATION:

    « NOTE La valeur recommandee (formule 6.6N) est normative. »

L'annexe rend la formule normative sans la reimprimer. Le texte est dans la
norme de base. Sans elle, la decision belge est tracable et son contenu ne
l'est pas.

Un role a part, et une regle qui ne bouge pas
-----------------------------------------------
``BASE_EUROCODE`` existait deja dans le modele et n'etait utilise par aucune
entree. Sa regle reste entiere: une valeur lue dans une norme de base est
``en_recommended``, jamais ``national_annex``, et ne peut donc jamais devenir
``confirmed``. Ce que ces documents apportent n'est pas une valeur nationale,
c'est le TEXTE d'une expression qu'une annexe designe.

Le fichier de base est un recueil
----------------------------------
``NBN_EN_1992-1-1_2005(F)+AC.pdf`` contient QUATRE documents distincts:

    p.   1-2    couvertures NBN (FR, NL)
    p.   3-6    avant-propos de l'ANB:2010 (FR p.3-4, NL p.5-6)
    p.   7-253  EN 1992-1-1:2004 (F), corps de la norme
    p. 254-255  couverture EN 1992-1-1:2004/AC:2010
    p. 256-279  « Modifications issues de l'EN 1992-1-1:2004/AC:2008
                (et modifiees par l'EN 1992-1-1:2004/AC:2010) »

Les corrigenda sont ANNEXES, pas fondus dans le corps. La verification est
directe et elle a ete faite: §6.2.5(2) du corps porte c = 0,25 / 0,35 / 0,45,
tandis que la modification n° 29 du corrigendum remplace ces valeurs. Lire le
corps sans lire les modifications donnerait donc le texte de 2004.

C'est enregistre en ``contained_layers`` pour qu'aucun lecteur futur ne prenne
le corps pour le texte applicable.

Lancer depuis tools/ndp_import/:
    python scripts/record_ec2_base_stack.py --dir DIR [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CATALOGUE = HERE / "src/ndp_import/data/catalogue.json"

#: Identite LUE en page de garde de chaque fichier, jamais deduite du nom.
STACK = [
    {
        "doc_key": "BE-EN199211-BASE",
        "filename": "NBN_EN_1992-1-1_2005(F)+AC.pdf",
        "reference": "NBN EN 1992-1-1:2005 (+AC:2010)",
        "title": (
            "Eurocode 2 : Calcul des structures en beton - Partie 1-1 : Regles "
            "generales et regles pour les batiments (+AC:2010)"
        ),
        "edition_read_from_cover": "1e ed., fevrier 2005 (LUE en page 1)",
        "indice": "B 15",
        "publication_authorised": "2005-01-26",
        "language": "fr",
        "contained_layers": [
            {"layer": "couvertures NBN (FR, NL)", "pages": "1-2"},
            {"layer": "avant-propos NBN EN 1992-1-1 ANB:2010", "pages": "3-6"},
            {"layer": "EN 1992-1-1:2004 (F), corps", "pages": "7-253"},
            {"layer": "EN 1992-1-1:2004/AC:2010, couverture", "pages": "254-255"},
            {"layer": "Modifications AC:2008 (+AC:2010), 120 entrees",
             "pages": "256-279"},
        ],
        "notes": (
            "PILE NORMATIVE. Les corrigenda sont ANNEXES et NON FONDUS dans le "
            "corps: verifie sur §6.2.5(2), ou le corps porte c = 0,25 / 0,35 / "
            "0,45 alors que la modification n° 29 les remplace. Lire le corps "
            "seul rend le texte de 2004. Les 120 modifications des pages "
            "256-279 sont la liste consolidee AC:2008 telle que modifiee par "
            "AC:2010 — son propre titre le dit."
        ),
    },
    {
        "doc_key": "BE-EN199211-A1",
        "filename": "NBN_EN_1992-1-1_A1_2014(E).pdf",
        "reference": "NBN EN 1992-1-1/A1 (2015)",
        "title": (
            "Amendement A1 a l'EN 1992-1-1:2004 — Eurocode 2, Partie 1-1"
        ),
        "edition_read_from_cover": "1e ed., fevrier 2015 (LUE en page 2)",
        "indice": "B 15",
        "publication_authorised": "2015-02-02",
        "language": "en",
        "contained_layers": [
            {"layer": "couvertures NBN (NL, FR)", "pages": "1-2"},
            {"layer": "EN 1992-1-1:2004/A1, decembre 2014", "pages": "3-9"},
        ],
        "notes": (
            "L'edition belge de fevrier 2015 porte l'amendement CEN "
            "EN 1992-1-1:2004/A1:2014, approuve le 8 novembre 2014. Les deux "
            "millesimes designent le meme texte. SEPT modifications, enumerees "
            "par son propre sommaire p.4: avant-propos, §3.3.2, §3.3.4, "
            "§6.4.5, §11.6.4.2, §12.6.5.2, §H.1.2. Aucune autre clause. "
            "L'amendement introduit un NDP NOUVEAU, k_max en §6.4.5(1), "
            "recommande 1,5 — POSTERIEUR a l'ANB:2010, qui ne peut donc pas "
            "l'avoir fixe. Point a verifier: l'ANB affirme p.5 que « tous les "
            "NDP sont fixes », ce qui etait vrai en 2010."
        ),
    },
    {
        "doc_key": "BE-EN199211-GEN2",
        "filename": "nbn_en_1992-1-1_2023_en.pdf",
        "reference": "NBN EN 1992-1-1:2023",
        "title": "Eurocode 2 (2e generation) - Part 1-1",
        "edition_read_from_cover": "2023 (LUE en page 1)",
        "indice": None,
        "publication_authorised": None,
        "language": "en",
        "contained_layers": [],
        "not_yet_applicable": True,
        "notes": (
            "DEUXIEME GENERATION, SANS FORCE EN BELGIQUE. Sa propre page 1: "
            "« This document does not replace the existing standard NBN EN "
            "1992-1-1:2005 and its amendment NBN EN 1992-1-1/A1:2015 ». Elle "
            "est publiee, numerotee, authentique, et en attente de son Annexe "
            "Nationale. NE JAMAIS l'utiliser pour un calcul belge. "
            "Sa page 1 rend un autre service, decisif: elle NOMME la pile de "
            "premiere generation — « Replaces ... NBN EN 1992-1-1/AC:2008, "
            "NBN EN 1992-1-1/AC:2010, ... NBN EN 1992-1-1/A1:2015, NBN EN "
            "1992-1-1:2005 ». C'est par elle qu'on a su qu'AC:2010 existait."
        ),
    },
]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv[1:])

    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    by_key = {e["doc_key"]: e for e in data["documents"]}
    recorded, missing = [], []

    for spec in STACK:
        path = args.dir / spec["filename"]
        if not path.exists():
            # Le fichier de 2e generation existe sous plusieurs noms selon
            # l'archive (« (1) », « (2) »). Chercher par prefixe avant
            # d'abandonner.
            stem = spec["filename"].rsplit(".", 1)[0]
            cands = sorted(args.dir.glob(f"{stem}*.pdf"))
            if not cands:
                missing.append(spec["filename"])
                continue
            path = cands[0]

        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entry = by_key.get(spec["doc_key"], {})
        entry.update({
            "doc_key": spec["doc_key"],
            "country_code": "BE",
            "standard_family": "EN 1992",
            "part": "1-1",
            "reference": spec["reference"],
            "title": spec["title"],
            "publisher": "NBN — Bureau de Normalisation",
            "document_role": "base_eurocode",
            "phase": "P2",
            # DEUX AXES, a ne pas confondre — et un premier jet les avait
            # confondus ici meme.
            #
            #   `status`      axe DOCUMENTAIRE: le fichier en main est-il le
            #                 texte publie qui gouverne, ou une consolidation
            #                 d'editeur, une copie de revendeur, un projet ?
            #   `document_role` axe NORMATIF: ce TYPE de document peut-il fixer
            #                 un parametre national ? Voir
            #                 DocumentRole.can_fix_national_parameters.
            #
            # Ils sont independants. Un Eurocode de base peut parfaitement
            # etre `acquired` — ces exemplaires portent « norme belge
            # enregistree » sans aucune reserve d'editeur — et rester incapable
            # de fixer un NDP. Le refus vient du ROLE, jamais du statut.
            #
            # Si l'on met ici `acquired_for_reading`, c'est pour la seule
            # raison qui vaille: l'identite a ete LUE par une machine sur une
            # page de garde et n'a ete DECLAREE par personne.
            "status": "acquired_for_reading",
            "edition_read_from_cover": spec["edition_read_from_cover"],
            "publication_authorised": spec["publication_authorised"],
            "language_read_from_cover": spec["language"],
            "doc_id_sha256": digest,
            "contained_layers": spec["contained_layers"],
            "parameters_expected": [],
            "acquisition": {
                "how": "Achat sur https://www.nbn.be.",
                "licence": "Document payant, non redistribuable.",
                "languages": [spec["language"]],
                "notes": (
                    f"Identite LUE en page de garde de {path.name}. "
                    + (f"Indice de classement NBN: {spec['indice']}. "
                       if spec["indice"] else "")
                    + spec["notes"]
                    + " ROLE: base_eurocode — porte le TEXTE des expressions "
                    "qu'une Annexe Nationale designe, ne fixe aucun parametre "
                    "national. Une valeur lue ici est en_recommended et ne peut "
                    "jamais devenir confirmed. "
                    # L'invariant vaut pour une norme de base autant que pour
                    # une annexe: l'identite ci-dessus a ete LUE par une
                    # machine sur une page de garde, elle n'a ete DECLAREE par
                    # personne. Un test du depot l'exige, et il a raison.
                    "IDENTITE A DECLARER par l'ingenieur qui depose."
                ),
            },
        })
        if spec.get("not_yet_applicable"):
            entry["not_yet_applicable"] = True
        if spec["doc_key"] not in by_key:
            data["documents"].append(entry)
            by_key[spec["doc_key"]] = entry
        recorded.append(f"{spec['doc_key']:20s} {spec['reference']:34s} "
                        f"{digest[:12]}  {path.name}")

    if not args.dry_run:
        CATALOGUE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print(f"{len(recorded)} document(s) de base enregistre(s):")
    for line in recorded:
        print("   " + line)
    if missing:
        print(f"\n{len(missing)} fichier(s) introuvable(s): {', '.join(missing)}")
    print("\nRappel: aucun de ces documents ne peut confirmer un parametre")
    print("national. Ils portent le texte, l'annexe porte la decision.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
