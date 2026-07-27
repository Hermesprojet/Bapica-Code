#!/usr/bin/env python3
"""Record every Belgian National Annex actually in hand.

Why this exists
---------------
The catalogue said three documents were acquired. Ten had been deposited and
read. So ``ndp-import catalogue`` kept listing, as "still to obtain", annexes
that were sitting in the deposit — and the same files were sent three times
over because the report gave no way to tell.

An inventory that under-reports what it holds is not a safe error: it wastes
the acquisition effort that is the whole point of the report.

What this does NOT do
---------------------
Marking a document acquired says "we hold this file", never "we trust its
values". Every parameter stays ``pending_verification``; strict mode stays
blocked. ``parameters_expected`` is left empty where no extraction patterns
have been written yet: claiming parameters we cannot search for would be the
same lie in the other direction.

Editions below are LUES sur la page de garde and remain A DECLARER by the
depositor — the pipeline never infers an edition from a file.

Run from tools/ndp_import/:
    python scripts/record_be_acquisitions.py [--dry-run]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CATALOGUE = HERE / "src/ndp_import/data/catalogue.json"

_COMMON = (
    "Metadonnees LUES sur la page de garde, a DECLARER par le deposant. "
    "Detenir ce fichier ne confirme aucune valeur: tous les parametres restent "
    "pending_verification tant qu'un ingenieur habilite n'a pas signe."
)

#: doc_key -> (sha256, edition read from cover, pages, language, note)
ACQUIRED: dict[str, tuple[str, str, int, str, str]] = {
    "BE-EN1990-NA": (
        "cc74a2b5d0acd99cdbeeaaccba1af80d660861a57c253c97b568893ec2116a66",
        "2e ed., janvier 2013", 33, "fr",
        "Base de calcul des structures: coefficients partiels et combinaisons "
        "d'actions. EDITION EN VIGUEUR. Sa page de garde porte « Remplace: "
        "NBN EN 1990 ANB (2007) »; autorisation de publication du 28 septembre "
        "2012. Annexe a la NBN EN 1990, 1e ed. juillet 2002, y compris "
        "l'amendement NBN EN 1990/A1:2006. La 1e edition (2007, 15 pages) est "
        "aussi detenue et enregistree comme edition anterieure — le moteur "
        "resout l'annexe par la date de reference du projet. "
        "Aucun motif d'extraction ecrit a ce jour.",
    ),
    "BE-EN199111-NA": (
        "16acbb56fcc160a3867ac000f91505a79724bed28f3ca58500cfcf06b7c9a58e",
        "1e ed., septembre 2007", 11, "fr",
        "Poids volumiques, charges d'exploitation. Aucun motif d'extraction "
        "ecrit a ce jour.",
    ),
    "BE-EN199112-NA": (
        "bb39ccad867e4cb183534719143f07dffd7ab71a17512137482dc841514c7808",
        "1e ed., mai 2008", 27, "fr",
        "Actions sur les structures exposees au feu. Aucun motif d'extraction "
        "ecrit a ce jour.",
    ),
    "BE-EN199113-NA": (
        "9a2880b2f489a9803e1fc73b2268a0306ce2c298b568f0c52eeb10872980c29d",
        "1e uitg., oktober 2007 (version neerlandaise)", 9, "nl",
        "Charges de neige. Version NEERLANDAISE: la version francaise n'a pas "
        "ete deposee. Aucun motif d'extraction ecrit a ce jour.",
    ),
    "BE-EN199114-NA": (
        "a406441e0b5b53b79e4d0940fef1df72a6617ac260dc5dcf7749070c4999ffaf",
        "1e uitg., december 2010 (version neerlandaise)", 63, "nl",
        "Actions du vent. Version NEERLANDAISE: la version francaise n'a pas "
        "ete deposee. Aucun motif d'extraction ecrit a ce jour.",
    ),
    "BE-EN19912-NA": (
        "25735718283606f39fec41fae861b95cbfefd9e795b3d2c86b0763221191c11e",
        "1e ed., octobre 2011", 43, "fr",
        "Actions sur les ponts dues au trafic. Hors perimetre P1 (batiment). "
        "Aucun motif d'extraction ecrit a ce jour.",
    ),
    # --- Reglementations nationales, hors systeme Eurocode -----------------
    # Elles ne portent pas de NDP mais fixent des EXIGENCES (une duree de
    # resistance au feu R, un compartimentage) que l'Eurocode presuppose sans
    # les donner. Sans elles, on sait calculer une poutre au feu et pas quelle
    # duree lui imposer.
    "BE-AR-FEU": (
        "63dc2ef0905b966dec980615aaee14aba39bf17f152d5e4acb405d97f6b07f5b",
        "Moniteur Belge du 15.07.2009, Ed. 2, p. 49369", 29, "fr+nl+de",
        "Arrete Royal — Annexe 6 « Normes de base » resistance au feu. "
        "Publie au Moniteur Belge, donc OPPOSABLE de plein droit, contrairement "
        "a une norme NBN qui doit etre rendue obligatoire. Fixe les exigences R "
        "par type et hauteur de batiment. Le PDF melange les trois langues "
        "nationales dans un meme flux de texte: un depouillement automatique "
        "devra les separer avant toute lecture.",
    ),
    "BE-NBN-S21-208-1": (
        "ba5ec888933fb68d4b96bb8ac73478bfecce5b665ec1b39d5014ea2c64ea66b9",
        "1e ed., mai 1995", 44, "fr+nl",
        "NBN S 21-208-1 — Evacuation de fumees et de chaleur (EFC), grands "
        "espaces interieurs non cloisonnes sur un niveau. Ne figurait pas au "
        "catalogue: le document etait en main, lisible, et invisible du "
        "rapport « a obtenir ». Edition de 1995: verifier qu'aucune revision "
        "n'est parue avant de s'en servir.",
    ),
    "BE-NBN-S21-204": (
        "129c5b7b8a7e6e8fececcae94dd3172f14fce4e2ce43329757544cafb7999d03",
        "edition NON LUE sur la page de garde", 50, "fr",
        "NBN S 21-204 — Protection incendie dans les batiments, batiments "
        "SCOLAIRES. La page de garde ne porte ni date ni numero d'edition "
        "reperable (50 pages, 19029 caracteres): l'edition reste A ETABLIR par "
        "le deposant et n'est pas deduite. Portee restreinte aux batiments "
        "scolaires, ce que le titre du catalogue ne disait pas.",
    ),
}


#: A second copy of a document already held, in another form. Recorded so it
#: is not deposited again, and so a reviewer knows another rendering exists —
#: a scan is worthless to the extractor but a human can read it, and may need
#: to when the machine-readable copy is in a language they do not work in.
#:
#: doc_key -> (sha256, pages, why it is kept)
ALTERNATE_COPIES: dict[str, tuple[str, int, str]] = {
    "BE-EN1990-NA": (
        "40a8eeac9471d7203e81ff8a03921e064775734a1ad2e7c468f8dff63f943b16", 15,
        "EDITION ANTERIEURE, 1e ed. septembre 2007, version texte francaise. "
        "Explicitement remplacee par la 2e ed. janvier 2013 (« Remplace: "
        "NBN EN 1990 ANB (2007) » en couverture). Conservee, non jetee: le "
        "moteur resout l'annexe applicable par la date de reference du projet, "
        "et une etude anterieure a 2013 releve de cette edition. NE DOIT PAS "
        "servir pour un projet courant.",
    ),
    "BE-EN199113-NA": (
        "2de1dc9e81459f818abb6a2b471cf2b21b4eb2f71dbc29da1af95d2ed2d2a7d4", 9,
        "Copie NUMERISEE (0 caractere extractible) du meme nombre de pages que "
        "la version texte neerlandaise detenue. Langue NON DETERMINEE: sans "
        "couche de texte ni metadonnees, elle ne peut pas etre etablie sans "
        "ROC, et elle n'est pas devinee. Inutilisable par l'extracteur; "
        "lisible par un humain.",
    ),
    "BE-EN199114-NA": (
        "72741c82c16446738f756e322be6786e9e856f839d0f550c2d7a502da1262f8d", 60,
        "Copie NUMERISEE (0 caractere extractible), 60 pages contre 63 pour la "
        "version texte neerlandaise detenue — l'ecart suggere une autre edition "
        "ou une autre langue, ce qui reste A ETABLIR et n'est pas devine. "
        "Inutilisable par l'extracteur; lisible par un humain.",
    ),
}


def _verify_against_deposit(deposit: Path) -> int:
    """Recompute every digest from the files and refuse on any mismatch.

    A digest that is *typed* is a digest that can be invented — and one was,
    in the first draft of this script: only the leading 16 characters were
    known from the triage output and the remainder was filled in. The values
    were well-formed, 64 hex characters, and completely false.

    Nothing in the repository could have caught that, because the deposited
    PDFs are not in it. So the digests are cross-checked here against the
    actual files whenever they are available, and this mode is what should be
    run before committing a change to the table above.
    """
    from ndp_import.model import SourceDocument

    have = {SourceDocument.digest(p): p.name for p in sorted(deposit.glob("*.pdf"))}
    bad = 0
    checks = [(k, v[0]) for k, v in ACQUIRED.items()]
    checks += [(f"{k} (copie alt.)", v[0]) for k, v in ALTERNATE_COPIES.items()]
    for key, sha in sorted(checks):
        if sha in have:
            print(f"  OK   {key:18s} {sha[:16]}...  {have[sha]}")
        else:
            bad += 1
            print(f"  FAUX {key:18s} {sha[:16]}...  AUCUN fichier depose "
                  f"n'a cette empreinte")
    print()
    if bad:
        print(f"{bad} empreinte(s) ne correspondent a aucun fichier. NE PAS "
              f"COMMITTER: une empreinte se calcule, elle ne se saisit pas.")
    else:
        print(f"{len(checks)} empreinte(s) verifiees contre les fichiers reels.")
    return 1 if bad else 0


def main(argv: list[str]) -> int:
    if "--verify" in argv:
        deposit = Path(argv[argv.index("--verify") + 1])
        return _verify_against_deposit(deposit)

    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    by_key = {e["doc_key"]: e for e in data["documents"]}

    missing = [k for k in ACQUIRED if k not in by_key]
    if missing:
        print("ERREUR: cles absentes du catalogue: " + ", ".join(missing))
        return 1

    for key, (sha, edition, pages, lang, note) in ACQUIRED.items():
        entry = by_key[key]
        entry["status"] = "acquired"
        entry["doc_id_sha256"] = sha
        entry["edition_read_from_cover"] = edition
        entry["acquisition"]["notes"] = (
            f"ACQUIS en version texte ({pages} pages, langue {lang}). "
            f"{_COMMON} {note}"
        )
        entry.setdefault("parameters_expected", [])

    for key in {k for k in ALTERNATE_COPIES}:
        by_key[key]["alternate_copies"] = []
    for key, (sha, pages, why) in ALTERNATE_COPIES.items():
        by_key[key]["alternate_copies"].append(
            {"doc_id_sha256": sha, "page_count": pages,
             # La 1e ed. d'EN 1990 EST lisible; les autres copies sont des scans.
             "machine_readable": key == "BE-EN1990-NA",
             "notes": why}
        )

    if "--dry-run" not in argv:
        CATALOGUE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    total = sum(1 for e in data["documents"] if e["status"] != "not_acquired")
    print(f"{len(ACQUIRED)} annexe(s) belge(s) marquee(s) acquises.")
    print(f"{len(ALTERNATE_COPIES)} copie(s) alternative(s) enregistree(s).")
    print(f"{total} document(s) en main au total dans le catalogue.")
    print()
    print("AUCUN parametre ne change de statut. Le mode strict reste bloque.")
    print("NBN EN 1997-1 ANB (geotechnique) reste le seul manque pour P1 en")
    print("Belgique: les fichiers deposes sous ce nom sont l'Eurocode de base,")
    print("un projet slovene, et une page d'appat au telechargement.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(HERE / "src"))
    raise SystemExit(main(sys.argv))
