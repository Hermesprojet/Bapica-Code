#!/usr/bin/env python3
"""Inventaire complet des Annexes Nationales d'un pays, ligne par ligne.

Ce que cet audit refuse de faire
---------------------------------
Il ne deduit RIEN. En particulier, il ne dresse pas la liste des parametres
« restant a extraire » d'une annexe qui n'a jamais ete ouverte: personne ne
sait ce qu'elle contient tant que personne ne l'a lue. Ecrire « 15 parametres
restants » pour l'ANB EC8-1 reviendrait a inventer un inventaire, c'est-a-dire
exactement ce que ce projet interdit.

Pour une annexe jamais lue, la colonne dit donc « inventaire non etabli », et
c'est le resultat le plus important de cet audit: 53 des 56 annexes belges
detenues sont dans cet etat.

Quatre etats, a ne pas confondre
---------------------------------
* DETENUE       — le PDF est sur le disque. Ne dit rien du contenu.
* INVENTORIEE   — quelqu'un l'a ouverte et a etabli la liste des parametres
                  qu'elle fixe, mais rien n'est arrive dans le moteur.
* TRANSCRITE    — ses parametres sont dans le jeu de donnees du moteur, avec
                  clause, page et statut de validation.
* CONFIRMEE     — un verificateur NOMME a valide ses valeurs, a une date.

Le quatrieme etat a fait apparaitre le deuxieme: l'ANB EC3 1-1 porte onze
parametres inventories et des regles non scalaires relevees page par page,
et pourtant le moteur n'en connait aucun. Confondre « lue » et « utilisable »
aurait masque seize parametres deja lus.

La presence d'un PDF ne fait passer aucune valeur a ``confirmed``. Le seul
chemin vers ``confirmed`` passe par un verificateur nominatif et une date.

Distinction que la colonne « source » rend visible
---------------------------------------------------
Un parametre peut porter une valeur sans qu'elle vienne de l'annexe:
``source_type = en_recommended`` signale une valeur RECOMMANDEE par l'Eurocode,
posee comme point de depart. C'est le cas le plus dangereux du lot — il a
l'apparence d'une donnee nationale. Cote francais, ``v_min_coeff`` etait dans
cet etat et le moteur calculait faux: la France prescrit 0,053/gamma_C la ou
la recommandation EN donne 0,035.

Lancer depuis tools/ndp_import/:
    python scripts/audit_annexes.py [--country BE] [--format texte|csv]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CATALOGUE = HERE / "src/ndp_import/data/catalogue.json"
ENGINE_DATA = HERE.parents[1] / "engine/src/eurostruct_engine/ndp/data"

#: Le nom du fichier depose est ecrit dans les notes par les enregistreurs
#: recents (« Identite PARSEE en page 1 de X.pdf »). Les entrees plus
#: anciennes n'en portent pas: la colonne dit « non trace », qui est un
#: constat d'audit et non un detail cosmetique — sans nom de fichier, on ne
#: peut pas remonter du catalogue au PDF sans passer par l'empreinte.
_FILENAME = re.compile(r"(?:de|dans)\s+([^\s,;]+\.pdf)", re.IGNORECASE)


def filename_of(entry: dict) -> str | None:
    note = (entry.get("acquisition", {}) or {}).get("notes") or ""
    m = _FILENAME.search(note)
    return m.group(1) if m else None


def sort_key(entry: dict) -> tuple:
    fam, part = entry.get("standard_family", ""), entry.get("part", "") or ""
    return (tuple(int(n) for n in re.findall(r"\d+", fam + " " + part)), part)


def load_engine_parameters(cc: str) -> dict[str, dict]:
    """Les parametres transcris dans le moteur, indexes par reference d'annexe."""
    path = ENGINE_DATA / f"{cc.lower()}.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {a["reference"]: a.get("parameters", {}) for a in data.get("annexes", [])}


#: Un parametre etiquete ``source_type = national_annex`` qui porte quand meme
#: des valeurs de l'EN. C'est l'etat le plus trompeur du jeu de donnees, et
#: ``w_max`` y est, en BE comme en FR: le tableau 7.1N-ANB n'etant pas lisible
#: sur l'exemplaire depouille, les variantes portent les valeurs du tableau
#: 7.1N de l'EN. La note le dit en capitales; le MODELE, lui, ne le dit pas.
#:
#: Detecter cela sur de la prose est un pis-aller assume. Le constat d'audit
#: qui en decoule est qu'il manque un champ: ``value_provenance`` distinguant
#: « valeur nationale lue » de « valeur d'attente ». Tant qu'il n'existe pas,
#: un module qui lit ``variants`` sans lire ``notes`` utilise des valeurs
#: europeennes en croyant appliquer l'annexe belge.
_VALEUR_D_ATTENTE = re.compile(
    r"CE QUI MANQUE|PAS CELLES DU|ne sont pas lisibles|non lisibles",
    re.IGNORECASE,
)


def classify(params: dict) -> dict[str, list[str]]:
    """Repartir les parametres d'une annexe lue selon ce qui leur manque."""
    out: dict[str, list[str]] = {
        "confirmes": [], "a_confirmer": [], "a_lire": [],
        "formule": [], "valeur_d_attente": [],
    }
    for name, p in sorted(params.items()):
        status = p.get("validation_status")
        note = p.get("notes") or ""
        if status == "confirmed":
            out["confirmes"].append(name)
        elif status == "not_representable":
            out["formule"].append(name)
        elif p.get("source_type") == "en_recommended":
            # Valeur presente, mais RECOMMANDEE par l'EN: la clause nationale
            # n'a jamais ete ouverte. Le cas v_min_coeff.
            out["a_lire"].append(name)
        elif _VALEUR_D_ATTENTE.search(note):
            out["valeur_d_attente"].append(name)
        elif p.get("parameter_value") is None and not p.get("variants"):
            out["valeur_d_attente"].append(name)
        else:
            out["a_confirmer"].append(name)
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="BE")
    ap.add_argument("--format", default="texte", choices=("texte", "csv"))
    args = ap.parse_args(argv[1:])
    cc = args.country.upper()

    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    rows = sorted(
        (e for e in data["documents"]
         if e["country_code"] == cc and e.get("document_role") == "national_annex"),
        key=sort_key,
    )
    engine = load_engine_parameters(cc)

    records = []
    for e in rows:
        std = f"{e['standard_family']}-{e['part']}".rstrip("-")
        status = e.get("status", "not_acquired")
        params = engine.get(e["reference"], {})
        cls = classify(params) if params else None
        records.append({
            "inventorie": list(e.get("parameters_expected") or []),
            "norme": std,
            "fichier": filename_of(e) or ("—" if status == "not_acquired"
                                          else "non trace"),
            "reference": e["reference"],
            "edition": str(e.get("edition_read_from_cover")
                           or e.get("edition") or "—").replace(" (PARSEE en page 1)", ""),
            "statut": status,
            "entry": e,
            "params": params,
            "cls": cls,
        })

    if args.format == "csv":
        w = csv.writer(sys.stdout)
        w.writerow(["norme", "fichier", "reference", "edition", "statut",
                    "params_transcrits", "params_inventories_non_transcrits",
                    "params_confirmes", "params_a_confirmer",
                    "clauses_non_analysees", "valeurs_d_attente",
                    "params_formule"])
        for r in records:
            c = r["cls"]
            w.writerow([
                r["norme"], r["fichier"], r["reference"], r["edition"], r["statut"],
                len(r["params"]) if c else 0,
                "" if c else (";".join(r["inventorie"]) or
                              ("" if r["statut"] == "not_acquired"
                               else "inventaire non etabli")),
                len(c["confirmes"]) if c else 0,
                ";".join(c["a_confirmer"]) if c else "",
                ";".join(c["a_lire"]) if c else "",
                ";".join(c["valeur_d_attente"]) if c else "",
                ";".join(c["formule"]) if c else "",
            ])
        return 0

    lus = [r for r in records if r["cls"]]
    detenues = [r for r in records if r["statut"] != "not_acquired"]
    # Inventoriee mais non transcrite: l'annexe a ete ouverte, la liste de ses
    # parametres existe au catalogue, et le moteur n'en connait rien.
    inventoriees = [r for r in detenues if not r["cls"] and r["inventorie"]]
    jamais = [r for r in detenues if not r["cls"] and not r["inventorie"]]

    print("=" * 78)
    print(f"AUDIT DES ANNEXES NATIONALES — {cc}")
    print("=" * 78)
    print(f"{len(records)} au catalogue | {len(detenues)} detenues | "
          f"{len(lus)} transcrites dans le moteur | "
          f"{len(inventoriees)} inventoriees non transcrites | "
          f"{len(jamais)} jamais ouvertes")
    print()
    print("DETENUE n'est pas LUE, et LUE n'est pas CONFIRMEE. La presence d'un")
    print("PDF ne fait passer aucune valeur a « confirmed »: le seul chemin y")
    print("menant passe par un verificateur NOMME et une date de verification.")
    print()

    print("-" * 78)
    print("1. INVENTAIRE — une ligne par annexe")
    print("-" * 78)
    print(f"{'norme':14s} {'reference':26s} {'edition':22s} {'statut':22s} params")
    for r in records:
        c = r["cls"]
        p = (f"{len(r['params'])} transcrits" if c else
             ("—" if r["statut"] == "not_acquired" else
              (f"{len(r['inventorie'])} inventories, 0 transcrit"
               if r["inventorie"] else "INVENTAIRE NON ETABLI")))
        print(f"{r['norme']:14s} {r['reference'][:26]:26s} "
              f"{r['edition'][:22]:22s} {r['statut']:22s} {p}")
    print()
    print("Fichiers deposes (pour remonter du catalogue au PDF):")
    for r in detenues:
        print(f"   {r['norme']:14s} {r['fichier']}")
    print()

    print("-" * 78)
    print("2. LES ANNEXES LUES — detail parametre par parametre")
    print("-" * 78)
    if not lus:
        print("   Aucune.")
    for r in lus:
        c, params = r["cls"], r["params"]
        print()
        print(f"### {r['reference']} — {r['edition']}   [{r['statut']}]")
        print(f"    {len(params)} parametres inventories")
        for label, key, why in (
            ("CONFIRMES (verificateur nomme + date)", "confirmes", None),
            ("A CONFIRMER — valeur lue dans l'annexe, non validee",
             "a_confirmer", "il manque un verificateur nomme et une date"),
            ("CLAUSE NON ANALYSEE — la valeur portee est la RECOMMANDATION EN",
             "a_lire", "l'annexe est en main; la clause n'a jamais ete ouverte"),
            ("VALEUR D'ATTENTE — la valeur portee N'EST PAS la valeur nationale",
             "valeur_d_attente",
             "un exemplaire lisible de la page. En attendant, les valeurs "
             "portees sont celles de l'EN sous une etiquette nationale"),
            ("FORMULE, PAS CONSTANTE — aucun document ne debloque",
             "formule", "le modele du moteur doit admettre une expression"),
        ):
            names = c[key]
            if not names:
                continue
            print(f"  [{label}] {len(names)}")
            if why:
                print(f"      -> {why}")
            for n in names:
                p = params[n]
                page = p.get("source_page")
                print(f"      {n:26s} {str(p.get('clause','')):34s} "
                      + (f"p. {page}" if page else "page non relevee"))
        nsf = r["entry"].get("non_scalar_findings")
        if nsf:
            print("  [REGLES NON SCALAIRES relevees dans ce document]")
            for k, v in nsf.items():
                print(f"      {k}: {str(v)[:150]}")

    print()
    print("-" * 78)
    print("3. INVENTORIEES MAIS NON TRANSCRITES DANS LE MOTEUR")
    print("-" * 78)
    if not inventoriees:
        print("   Aucune.")
    for r in inventoriees:
        print(f"   {r['norme']:12s} {r['reference'][:28]:30s} "
              f"{len(r['inventorie'])} parametres inventories, aucun dans le moteur")
        for n in r["inventorie"]:
            print(f"        {n}")
        nsf = r["entry"].get("non_scalar_findings")
        for k, v in (nsf or {}).items():
            print(f"      [non scalaire] {k}: {str(v)[:150]}")
    print()
    print("Ces annexes ONT ete ouvertes: la liste ci-dessus vient d'une lecture,")
    print("pas d'une deduction. Ce qui manque n'est ni le document ni la")
    print("lecture, mais la transcription dans le jeu de donnees du moteur —")
    print("avec, pour chaque parametre, clause, page, valeur et statut.")
    print()

    print("-" * 78)
    print("4. DETENUES MAIS JAMAIS OUVERTES")
    print("-" * 78)
    print(f"{len(jamais)} annexes. Pour chacune, l'inventaire des parametres")
    print("n'est PAS etabli — et cet audit ne l'invente pas. Personne ne sait")
    print("quelles clauses elles fixent tant que personne ne les a lues.")
    print()
    for r in jamais:
        print(f"   {r['norme']:14s} {r['reference'][:30]:32s} {r['edition'][:24]}")
    print()
    print("Ce que chacune peut cacher: cote francais, l'ouverture de l'annexe")
    print("EC2 1-1 a montre que v_min_coeff valait 0,053/gamma_C et non 0,035.")
    print("Le moteur calculait FAUX en silence. Chaque ligne ci-dessus est un")
    print("risque de la meme nature, non encore leve.")

    print()
    print("-" * 78)
    print("5. EDITIONS — ce qui est ouvert")
    print("-" * 78)
    any_edition = False
    for r in records:
        e = r["entry"]
        for c in e.get("superseded_copies", []):
            any_edition = True
            print(f"   {r['norme']:12s} ed. {c['edition'][:28]:30s} CLOSE le "
                  f"{c.get('effective_to')} -> {c.get('superseded_by')}")
        for c in e.get("concurrent_copies", []):
            any_edition = True
            print(f"   {r['norme']:12s} ed. {c['edition'][:28]:30s} "
                  f"{c['relation_to_current']} | fait foi: {c['governing_edition']}")
            if c.get("missing_evidence"):
                print(f"        piece manquante: {c['missing_evidence'][:160]}")
    if not any_edition:
        print("   Aucune question d'edition ouverte.")

    print()
    print("-" * 78)
    print("6. CE QUI MANQUE, PAR NATURE")
    print("-" * 78)
    manquantes = [r for r in records if r["statut"] == "not_acquired"]
    print(f"A ACHETER ({len(manquantes)}):")
    for r in manquantes:
        print(f"   {r['norme']:14s} {r['reference']}")
    tot_lire = sum(len(r["cls"]["a_lire"]) for r in lus)
    tot_conf = sum(len(r["cls"]["a_confirmer"]) for r in lus)
    tot_page = sum(len(r["cls"]["valeur_d_attente"]) for r in lus)
    tot_form = sum(len(r["cls"]["formule"]) for r in lus)
    print(f"A LIRE — clauses jamais ouvertes dans une annexe EN MAIN: {tot_lire}")
    print(f"A CONFIRMER — valeurs lues, verificateur nomme manquant: {tot_conf}")
    print(f"VALEUR D'ATTENTE — valeur portee non nationale: {tot_page}")
    print(f"FORMULE — developpement, pas acquisition: {tot_form}")
    tot_inv = sum(len(r["inventorie"]) for r in inventoriees)
    print(f"A TRANSCRIRE — parametres lus, absents du moteur: {tot_inv} "
          f"(dans {len(inventoriees)} annexes)")
    print(f"INVENTAIRE NON ETABLI — annexes detenues jamais ouvertes: {len(jamais)}")
    print()
    print("Les trois premieres lignes se resolvent par une LECTURE humaine.")
    print("La quatrieme par du CODE. La cinquieme est la plus large et la")
    print("moins visible: elle ne se compte pas en parametres, parce que")
    print("personne ne sait encore combien il y en a.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
