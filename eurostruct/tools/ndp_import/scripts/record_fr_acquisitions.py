#!/usr/bin/env python3
"""Record the French National Annexes actually in hand.

Only ONE so far, and the reason the others are not here matters more than the
one that is.

France arrived in four different broken shapes, each a different lesson:

* ``NF EN 1992-1-1/NA`` — the P0 blocker — came as a **publisher's
  consolidation** whose own cover says « seules les Normes individuellement
  homologuees et composant cette compilation font foi ». It is readable and it
  is not the text that governs. It also carries a per-page licence watermark
  naming another organisation and a user's IP address.
* ``NF EN 1991-1-4/NA`` came with a **broken font encoding**: « NF EN
  1991-1-4/NA » extracts as « ÒÚ ÛÒ ïççïóïóìñÒß ».
* ``NF EN 1990/NA`` came as a **Google translation** of NF P 06-100-2, stamped
  as such, with spaces injected inside its own identifiers.
* ``NF EN 1991-1-3/NA`` came twice: once genuine (AFNOR 2007, below) and once
  as a consolidation carrying amendments A1:2011 and A2:2022.

That last pair is the uncomfortable one. The authentic file is the 2007 base
WITHOUT its two amendments; the current content exists only in a consolidation
licensed to a third party. We register the authentic one and say plainly that
it is incomplete — an honest gap beats a complete document nobody may use.

Run from tools/ndp_import/:
    python scripts/record_fr_acquisitions.py [--verify DIR] [--dry-run]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CATALOGUE = HERE / "src/ndp_import/data/catalogue.json"

ACQUIRED: dict[str, tuple[str, str, int, str, str]] = {
    "FR-EN199113-NA": (
        "72e8940932f90b6a051b2f8a677438bcf873413646f4f7ffb3207b517d6bc026",
        "mai 2007, 1er tirage 2007-05-F", 12, "fr",
        "Charges de neige. Document AFNOR AUTHENTIQUE: © AFNOR 2007, "
        "FA151261, ISSN 0335-3931, indice de classement P 06-113-1/NA, "
        "ICS 91.010.30 ; 91.080.01. Annexe a la NF EN 1991-1-3:2004. "
        "INCOMPLET: c'est l'edition de base de mai 2007, SANS les amendements "
        "A1 (juillet 2011) ni A2 (juillet 2022) dont l'existence est connue "
        "par une consolidation d'editeur deposee en parallele. Avant tout "
        "usage sur un projet courant, obtenir ces deux amendements aupres "
        "d'AFNOR. Aucun parametre n'est renseigne a partir de ce document.",
    ),
}


#: Files held for DEVELOPMENT, not as the text that governs.
#:
#: The distinction is the point. These are readable renderings — publisher's
#: consolidations, a copy licensed to another organisation, a machine
#: translation — and every one of them is enough to build the application
#: against: locate the clauses, know which parameters exist, size the review
#: dossier, write the extraction patterns. None may back a confirmed value;
#: ``to_engine_records`` refuses on ``is_authoritative = False``.
#:
#: doc_key -> (sha256, edition read from cover, pages, what it is, what it is not)
FOR_READING: dict[str, tuple[str, str, int, str]] = {
    "FR-EN199211-NA": (
        "debec24823773719ea42af45b90fb88ca68860433c169ffe94b72f366a82727f",
        "mars 2016 + amendement A1 (novembre 2022)", 40,
        "NF EN 1992-1-1/NA, indice P 18-711-1/NA. Consolidation Batipedia "
        "(CSTB Editions), licenciee a UNIVERSITE DE BORDEAUX, filigranee par "
        "page avec l'adresse IP d'un utilisateur. Sa couverture declare: "
        "« seules les Normes individuellement homologuees et composant cette "
        "compilation font foi ». C'est LE bloquant P0 francais: le contenu est "
        "complet et lisible, il sert a batir l'application, et une licence "
        "AFNOR au nom du bureau d'etudes reste requise avant toute etude.",
    ),
    "FR-EN1990-NA": (
        "7f94f0767d1d947ac6b3dc5238db805228f2578df386caad93d10ff135526cda",
        "juin 2004 (NF P 06-100-2), rendu anglais", 10,
        "TRADUCTION AUTOMATIQUE Google d'un document AFNOR francais, "
        "estampillee comme telle. A n'utiliser QUE pour reperer la structure, "
        "et encore avec mefiance: la machine injecte des espaces dans les "
        "identifiants (« P 0 6-100-2 », « N F EN 1 990 »), donc les nombres "
        "sont suspects par construction. AUCUNE valeur n'en sera tiree, meme "
        "en developpement.",
    ),
    "FR-EN199114-NA": (
        "7e66eef6dcc43d4d1f374b05021580184d8049b300a69243ec60d504d908002c",
        "mars 2008", 43,
        "NF EN 1991-1-4/NA. Couche de texte SYSTEMATIQUEMENT MAL DECODEE: la "
        "police ne porte pas de table Unicode valide et « NF EN 1991-1-4/NA » "
        "ressort « ÒÚ ÛÒ ïççïóïóìñÒß ». Inexploitable meme pour la structure. "
        "Enregistre pour que le fichier ne soit pas redepose: c'est une AUTRE "
        "version qu'il faut.",
    ),
}


def _verify(deposit: Path) -> int:
    """Recompute each digest from the files. A digest typed is a digest invented."""
    from ndp_import.model import SourceDocument

    have = {SourceDocument.digest(p): p.name for p in sorted(deposit.glob("*.pdf"))}
    bad = 0
    checks = [(k, v[0]) for k, v in ACQUIRED.items()]
    checks += [(f"{k} (lecture)", v[0]) for k, v in FOR_READING.items()]
    for key, sha in sorted(checks):
        if sha in have:
            print(f"  OK   {key:18s} {sha[:16]}...  {have[sha]}")
        else:
            bad += 1
            print(f"  FAUX {key:18s} {sha[:16]}...  aucun fichier depose")
    print()
    print(f"{len(checks) - bad}/{len(checks)} empreinte(s) verifiees.")
    return 1 if bad else 0


def main(argv: list[str]) -> int:
    if "--verify" in argv:
        return _verify(Path(argv[argv.index("--verify") + 1]))

    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    by_key = {e["doc_key"]: e for e in data["documents"]}

    for key, (sha, edition, pages, lang, note) in ACQUIRED.items():
        entry = by_key[key]
        entry["status"] = "acquired"
        entry["doc_id_sha256"] = sha
        entry["edition_read_from_cover"] = edition
        entry["acquisition"]["notes"] = (
            f"ACQUIS en version texte ({pages} pages, langue {lang}). "
            "Metadonnees LUES sur la page de garde, a DECLARER par le "
            "deposant. Detenir ce fichier ne confirme aucune valeur: tous les "
            f"parametres restent pending_verification. {note}"
        )
        entry.setdefault("parameters_expected", [])

    for key, (sha, edition, pages, note) in FOR_READING.items():
        entry = by_key[key]
        # Statut distinct: le fichier est DETENU et LISIBLE, il ne FAIT PAS FOI.
        # CatalogueEntry.is_authoritative ne renvoie vrai que pour 'acquired'.
        entry["status"] = "acquired_for_reading"
        entry["doc_id_sha256"] = sha
        entry["edition_read_from_cover"] = edition
        entry["acquisition"]["notes"] = (
            f"DETENU POUR LECTURE SEULE ({pages} pages). Ne FAIT PAS FOI: "
            "sert a batir l'application — reperer les clauses, connaitre les "
            "parametres, dimensionner le dossier de relecture. Aucune valeur "
            "confirmee ne peut s'y appuyer (to_engine_records refuse). "
            "Metadonnees LUES sur la page de garde, a DECLARER par le "
            f"deposant. {note}"
        )
        entry.setdefault("parameters_expected", [])

    if "--dry-run" not in argv:
        CATALOGUE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    fr = [e for e in data["documents"] if e["country_code"] == "FR"]
    print(f"{len(ACQUIRED)} annexe(s) francaise(s) qui FAIT FOI.")
    print(f"{len(FOR_READING)} fichier(s) en LECTURE SEULE, pour batir l'app.")
    print(f"France: {sum(1 for e in fr if e['status'] != 'not_acquired')}/{len(fr)} "
          f"en main.")
    print()
    print("NF EN 1992-1-1/NA — le bloquant P0 francais — est en LECTURE SEULE:")
    print("consolidation d'editeur qui declare elle-meme ne pas faire foi, et")
    print("porte le filigrane de licence d'un tiers. Elle suffit a batir")
    print("l'application; une licence AFNOR au nom du bureau d'etudes reste")
    print("requise avant d'emettre une etude.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(HERE / "src"))
    raise SystemExit(main(sys.argv))
