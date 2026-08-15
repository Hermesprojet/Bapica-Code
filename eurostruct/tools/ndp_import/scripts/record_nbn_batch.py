#!/usr/bin/env python3
"""Register Belgian National Annexes, and detect the ones they supersede.

The NBN cover is regular and says more than AFNOR's:

    Norme belge NBN EN 1990 ANB:2021 ... Valable a partir de 23-03-2021
    Remplace NBN EN 1990 ANB:2013

That third line is the reason this script exists rather than a variant of the
French one. AFNOR's covers do not name the edition they replace, so a
superseded copy in the catalogue can only be found by someone noticing. NBN
prints it, so it can be checked mechanically — and it has to be, because the
failure it prevents is the worst one this catalogue can suffer.

The failure in question, found on the first run
------------------------------------------------
``NBN EN 1990 ANB`` was held in its 2013 edition at status ``acquired`` — the
status that means a value read from it may be CONFIRMED. The 2021 edition says,
on its own cover, that it replaces 2013. A study signed on the 2013 values would
have cited an annex withdrawn five years earlier, and nothing in the pipeline
would have said so.

An external register had claimed the 2021 edition existed. That claim was
recorded as a flag and explicitly NOT acted upon, because the register named no
document and no URL. It turned out to be right, to the day: 2021-03-23. Being
right is not the same as being verifiable, and the flag was the correct response
to an unverifiable claim — the document is what settles it.

What happens to a superseded edition
--------------------------------------
It is closed, not deleted. ``effective_to`` is set to the day before the new
edition takes effect, its digest moves to ``superseded_copies``, and the note
says which edition replaced it and on what date. Ten-year liability means a
study signed in 2019 was signed against the 2013 annex, and that has to stay
readable.

... and what happens when the cover writes the future tense
------------------------------------------------------------
Nothing is closed. The EC6 deposit brought this sentence:

    Cette norme remplaceRA le NBN EN 1996-1-2 ANB:2012.

In Belgium a standard becomes binding only through homologation published in
the Moniteur belge. NBN writes "remplace" once that has happened and
"remplacera" while it has not, and the difference is two letters. Closing the
2012 edition on the strength of a future tense would mean dating a royal
decree nobody has read — inventing precisely the thing that is missing. Both
editions stay held, ``governing_edition`` is ``pending_verification``, and
``missing_evidence`` names the document that would settle it.

Three further shapes this deposit made necessary
-------------------------------------------------
* ``NBN EN 1996-1-1+A1 ANB`` — the annex to the AMENDED standard. It files
  under the unamended entry, because the annex to EN 1996-1-1+A1 is the annex
  to EN 1996-1-1; a twin entry would never have compared its edition with the
  2010 one sitting next to it.
* ``Remplace X:2010 et Y:2014`` — two references after one verb. Only the
  first was read.
* ``Document NBN/DTD ... technique belge`` — published, numbered, and without
  force: its own cover says the content is that of the prNBN draft under
  public enquiry. Refused. But the guard is anchored on the document's own
  designation, because the genuine 2016 annex CITES the DTD in its "Remplace"
  line, and a looser rule refused exactly the document that was wanted.

Run from tools/ndp_import/:
    python scripts/record_nbn_batch.py --dir DIR [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from record_fr_reef4_annexes import _mirror_to_other_countries  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
CATALOGUE = HERE / "src/ndp_import/data/catalogue.json"

#: La reference d'une annexe belge, sous les quatre formes rencontrees:
#:
#:     NBN EN 1990 ANB          la forme ordinaire
#:     NBN EN 1991-1-2-ANB      tiret au lieu de l'espace, un seul document
#:     NBN EN 1996-1-1+A1 ANB   annexe de la norme AMENDEE
#:     NBN/DTD EN 1996-1-1+A1 ANB   document technique, voir _is_dtd
#:
#: Le suffixe « +A1 » a coute cher: le depot de l'EC6 a apporte
#: « NBN EN 1996-1-1+A1 ANB:2016 », qui remplace l'edition 2010, et l'ancienne
#: expression ne le reconnaissait pas. Resultat: le fichier etait IGNORE en
#: silence, l'edition 2010 restait enregistree comme l'annexe belge de
#: l'EN 1996-1-1, et le catalogue affirmait detenir une edition que le
#: document en main declare remplacee depuis le 12-05-2016. C'est exactement
#: la panne que ce script avait ete ecrit pour empecher, revenue par une forme
#: que l'expression ne couvrait pas.
_REF = r"NBN(?:/DTD)?\s+EN\s+[\d-]+(?:\+A\d)?(?:/A\d)?[\s-]ANB"

_SELF = re.compile(
    rf"Norme\s+belge\s+(?P<ref>{_REF})\s*:\s*(?P<year>\d{{4}})",
    re.IGNORECASE,
)
#: « Valable a partir de 23-03-2021 ». Un premier jet acceptait « d » et
#: « du » mais pas « de », et rendait une date vide sur TOUS les documents
#: recents sans rien signaler.
_VALID_FROM = re.compile(
    r"Valable\s+(?:a|à)\s+partir\s+d[eu]?\s+(\d{2})-(\d{2})-(\d{4})",
    re.IGNORECASE,
)

#: Le separateur avant « ANB » est une espace sur dix-sept documents et un
#: TIRET sur un seul: « NBN EN 1991-1-2-ANB ». Variation typographique de
#: l'editeur, pas du sens.
#:
#: Couverture ANCIENNE (2007-2013), tout autre: la reference precede la
#: mention « Norme belge », l'edition s'ecrit en toutes lettres, et il y a un
#: INDICE DE CLASSEMENT — « B 51 », « B 03 ». Contrairement a ce que j'avais
#: affirme, le NBN en attribue donc un; il est bien plus large que l'indice
#: AFNOR (une famille, pas un document) mais il existe.
_SELF_OLD = re.compile(
    rf"(?P<ref>{_REF})\s+Norme\s+belge\s+"
    r"(?P<edition>\d+e?\s+(?:ed|éd)\.?,?\s+[a-zéû]+\s+(?P<year>\d{4}))",
    re.IGNORECASE,
)
_INDICE_BE = re.compile(r"Indice\s+de\s+classement\s*:\s*([A-Z]\s?\d+)",
                        re.IGNORECASE)

#: « Remplace » ou « remplaceRA ». Le futur n'est pas une coquille de
#: l'editeur, c'est un etat distinct, et le NBN ecrit les deux:
#:
#:     NBN EN 1996-1-1+A1 ANB:2016 — « Remplace NBN EN 1996-1-1 ANB:2010 et
#:                                     NBN/DTD EN 1996-1-1+A1 ANB:2014 »
#:     NBN EN 1996-1-2 ANB:2019    — « Cette norme remplaceRA le
#:                                     NBN EN 1996-1-2 ANB:2012. »
#:
#: En Belgique une norme ne devient obligatoire que par homologation publiee
#: au Moniteur belge. Le futur dit: publiee, homologation non encore acquise.
#: Clore l'edition ancienne sur la foi d'un futur reviendrait a declarer
#: perime un document qui reste peut-etre le seul en vigueur — donc a inventer
#: la date d'un arrete royal que personne n'a lu.
#:
#: Deux references peuvent suivre le verbe, separees par « et ». Une seule
#: etait lue: sur la couverture 2016, le DTD 2014 passait a la trappe.
_REPLACES_CLAUSE = re.compile(
    r"(?:Cette\s+norme\s+)?Remplace(?P<future>ra)?\s+(?P<list>[^.]*)",
    re.IGNORECASE,
)
_REPLACED_REF = re.compile(rf"(?P<ref>{_REF})\s*:\s*(?P<year>\d{{4}})",
                           re.IGNORECASE)

#: « Document NBN/DTD ... technique belge ». Ce n'est pas une norme: sa propre
#: couverture dit que son contenu est « identique a celui du projet de norme
#: prNBN ... mis a l'enquete publique », et qu'une norme le remplacera apres
#: homologation. Un projet publie sous une autre couverture reste un projet.
#:
#: ANCRE SUR « Document » — et la raison merite d'etre ecrite, parce que le
#: premier jet a refait, dans ce fichier, la faute que triage.py documente
#: pour _SUPERSEDES. « NBN/DTD » nu matchait aussi la CITATION que porte la
#: couverture de 2016: « Remplace NBN EN 1996-1-1 ANB:2010 et NBN/DTD
#: EN 1996-1-1+A1 ANB:2014 ». L'annexe authentique de 2016 — celle qu'on
#: attend — etait refusee parce qu'elle nomme le projet qu'elle remplace.
#: Nommer un document n'est pas en etre un.
_IS_DTD_SELF = re.compile(r"Document\s+NBN\s*/\s*DTD\s+EN", re.IGNORECASE)
_IS_DTD_ANY = re.compile(r"NBN\s*/\s*DTD", re.IGNORECASE)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _year_of(edition: str) -> str | None:
    """L'annee d'une edition, ecrite « 2016 » ou « 1e ed., novembre 2010 »."""
    years = re.findall(r"(?:19|20)\d{2}", edition or "")
    return years[-1] if years else None


def identify(path: Path) -> dict | None:
    with pdfplumber.open(str(path)) as pdf:
        front = _norm(pdf.pages[0].extract_text() or "")

    me = _SELF.search(front)
    old = None if me else _SELF_OLD.search(front)

    # Le document se designe lui-meme comme DTD, ou bien il porte « NBN/DTD »
    # sans jamais se dire « Norme belge » — auquel cas la mention ne peut pas
    # etre une citation faite par une norme.
    if _IS_DTD_SELF.search(front) or (_IS_DTD_ANY.search(front) and not (me or old)):
        print(f"  REFUSE {path.name}: « Document NBN/DTD ... technique belge ». "
              "Sa couverture declare son contenu identique au projet de norme "
              "prNBN mis a l'enquete publique, et annonce qu'une norme le "
              "remplacera apres homologation au Moniteur belge. Un projet "
              "publie sous une autre couverture reste un projet: aucune valeur "
              "nationale ne peut en etre tiree.")
        return None

    if not (me or old):
        print(f"  IGNORE {path.name}: ni « Norme belge NBN ... ANB:AAAA » "
              "ni « NBN ... ANB Norme belge Ne ed., ... »")
        return None

    vf = _VALID_FROM.search(front)
    ind = _INDICE_BE.search(front)
    clause = _REPLACES_CLAUSE.search(front)
    replaced = (
        [
            {"reference": _norm(m.group("ref")), "year": m.group("year")}
            for m in _REPLACED_REF.finditer(clause.group("list"))
        ]
        if clause else []
    )
    ref = _norm((me or old).group("ref"))
    # Le « +A1 » appartient a la REFERENCE, pas a la partie. L'annexe de
    # l'EN 1996-1-1+A1 est l'annexe de l'EN 1996-1-1 amendee, pas celle d'une
    # norme distincte: elle doit retomber sur la meme entree BE-EN199611-NA,
    # sans quoi le depot creerait une entree jumelle et les deux editions
    # cohabiteraient sans jamais se rencontrer.
    std = re.sub(r"\+A\d", "", ref)
    std = std.replace("NBN ", "").replace(" ANB", "").replace("-ANB", "").strip()
    family, _, part = std.partition("-")
    if family.startswith("EN 1990") or " " not in std:
        family, part = std, ""
    else:
        family = "EN " + std.split()[1].split("-")[0]
        part = std.split("-", 1)[1] if "-" in std.split()[1] else ""

    edition = (
        me.group("year") if me else _norm(old.group("edition"))
    )
    return {
        "reference": ref, "edition": edition,
        "edition_year": (me.group("year") if me else old.group("year")),
        "indice": _norm(ind.group(1)) if ind else None,
        "effective_from": (f"{vf.group(3)}-{vf.group(2)}-{vf.group(1)}" if vf else None),
        "replaces": [f"{r['reference']}:{r['year']}" for r in replaced],
        "replaces_years": [r["year"] for r in replaced],
        # « remplacera »: annonce, pas effet. Voir _REPLACES_CLAUSE.
        "supersession_is_effective": bool(clause and not clause.group("future")),
        "standard_family": family, "part": part,
        "doc_id_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "filename": path.name,
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv[1:])

    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    by_key = {e["doc_key"]: e for e in data["documents"]}

    recorded, superseded, skipped, created = [], [], [], []
    duplicates: list[str] = []
    announced: list[str] = []
    groups: dict[str, list[dict]] = {}
    for path in sorted(args.dir.glob("*ANB*.pdf")):
        ident = identify(path)
        if ident is None:
            skipped.append(path.name)
            continue
        flat = (ident["standard_family"] + ident["part"]).replace(" ", "").replace("-", "")
        groups.setdefault(f"BE-{flat}-NA", []).append(ident)

    for key, idents in groups.items():
        # Plusieurs fichiers pour une meme entree, trois cas et non deux.
        #
        # 1. Doublon exact — « ..._ANB_2011(F).pdf » et « ... (1).pdf »,
        #    octet pour octet identiques. Sans consequence, signale.
        # 2. Deux EDITIONS de la meme annexe: 2012 et 2019 pour l'EN 1996-1-2.
        #    Un premier jet criait CONFLIT et n'en retenait AUCUNE — la
        #    Belgique se retrouvait sans annexe EC6 feu alors qu'on en detient
        #    deux. La garde avait ete ecrite pour le cas 1 et la succession
        #    d'editions, qui est la vie normale d'une norme, y tombait.
        # 3. Deux fichiers DIFFERENTS de meme edition: la, rien n'est retenu.
        by_digest: dict[str, dict] = {}
        for ident in idents:
            d = ident["doc_id_sha256"]
            if d in by_digest:
                duplicates.append(
                    f"{key}: {ident['filename']} = {by_digest[d]['filename']}")
            else:
                by_digest[d] = ident
        unique = list(by_digest.values())

        editions = {i["edition_year"] for i in unique}
        if len(unique) > 1 and len(editions) < len(unique):
            print(f"  CONFLIT sur {key}: "
                  + ", ".join(sorted(i["filename"] for i in unique))
                  + " revendiquent la MEME edition et different. "
                  "Aucun n'est retenu.")
            skipped.extend(i["filename"] for i in unique)
            continue

        # La plus recente devient l'exemplaire courant; les autres sont
        # traitees ensuite, chacune selon ce que la couverture recente en dit.
        unique.sort(key=lambda i: (i["effective_from"] or "", i["edition_year"]))
        older, ident = unique[:-1], unique[-1]

        entry = by_key.get(key)
        if entry is None:
            # Le depot cree l'entree, comme cote francais. Refuser aurait
            # oblige a une intervention manuelle a chaque nouvelle partie —
            # EN 1993-4-2 et 4-3 sont arrivees ainsi, et aucune phase ne les
            # prevoyait.
            entry = {
                "doc_key": key, "country_code": "BE",
                "standard_family": ident["standard_family"],
                "part": ident["part"], "reference": ident["reference"],
                "title": f"Annexe Nationale — {ident['reference']}",
                "publisher": "NBN — Bureau de Normalisation",
                "acquisition": {
                    "how": "Achat sur https://www.nbn.be.",
                    "licence": "Document payant, non redistribuable.",
                    "languages": ["fr", "nl"], "notes": "",
                },
                "parameters_expected": [], "phase": "P2",
                "document_role": "national_annex", "status": "not_acquired",
            }
            data["documents"].append(entry)
            by_key[key] = entry
            created.append(key)

        acq = entry.setdefault("acquisition", {})
        previous_note = (acq.get("notes") or "").strip()
        previous_edition = str(
            entry.get("edition_read_from_cover") or entry.get("edition") or ""
        )
        previous_digest = entry.get("doc_id_sha256")

        # Le document dit lui-meme ce qu'il remplace. Trois sorties, et une
        # seule ferme l'edition ancienne.
        #
        #   « Remplace X:AAAA »    -> X est PERIMEE, close par effective_to.
        #   « remplaceRA X:AAAA »  -> annonce. L'homologation au Moniteur belge
        #                             n'est pas lue: laquelle des deux fait foi
        #                             reste pending_verification.
        #   rien sur X             -> on detient deux editions et la recente ne
        #                             dit rien de l'ancienne. Meme reponse.
        #
        # Une edition ancienne n'est jamais supprimee: dix ans de
        # responsabilite decennale exigent qu'une etude signee sous elle reste
        # lisible.
        closed: list[str] = []
        held_alongside: list[str] = []

        def _older_copy(ref: str, edition: str, digest: str | None) -> None:
            year = "".join(c for c in edition if c.isdigit())[-4:]
            named = year and year in ident["replaces_years"]
            if named and ident["supersession_is_effective"]:
                eff = ident["effective_from"]
                entry.setdefault("superseded_copies", []).append({
                    "reference": ref, "edition": edition,
                    "doc_id_sha256": digest,
                    "effective_to": (
                        (date.fromisoformat(eff) - timedelta(days=1)).isoformat()
                        if eff else None
                    ),
                    "superseded_by": f"{ident['reference']}:{ident['edition']}",
                })
                closed.append(f"{ref} ed. {edition}")
                superseded.append(
                    f"{ref} ed. {edition} -> remplacee par "
                    f"{ident['reference']}:{ident['edition']}")
                return
            entry.setdefault("concurrent_copies", []).append({
                "reference": ref, "edition": edition,
                "doc_id_sha256": digest,
                "relation_to_current": (
                    "annoncee_remplacee" if named else "non_mentionnee"),
                "governing_edition": "pending_verification",
                "missing_evidence": (
                    "Date d'homologation publiee au Moniteur belge. La "
                    f"couverture de {ident['edition']} ecrit « remplaceRA », "
                    "au futur: la publication par le NBN est acquise, "
                    "l'homologation qui rend la norme obligatoire ne l'est "
                    "pas. Sans arrete royal lu, laquelle des deux editions "
                    "fait foi ne peut etre affirmee."
                    if named else
                    f"Mention explicite du sort de l'edition {edition}. La "
                    f"couverture de {ident['edition']} ne la nomme pas: rien "
                    "dans le document en main ne permet de la declarer "
                    "perimee, ni de la declarer en vigueur."
                ),
            })
            held_alongside.append(f"{ref} ed. {edition}")
            announced.append(
                f"{key}: {ident['edition']} et {edition} detenues, laquelle "
                f"fait foi = pending_verification "
                f"({'« remplacera », au futur' if named else 'sans mention'})")

        # L'exemplaire deja au catalogue n'est pas forcement le plus ancien:
        # rien n'empeche de deposer en second une edition anterieure. Le
        # comparer par l'annee avant d'en tirer quoi que ce soit, faute de
        # quoi un depot dans le desordre ferait RECULER le catalogue.
        prev_year = _year_of(previous_edition)
        if previous_digest and previous_digest != ident["doc_id_sha256"]:
            if prev_year and prev_year > ident["edition_year"]:
                entry.setdefault("concurrent_copies", []).append({
                    "reference": ident["reference"], "edition": ident["edition"],
                    "doc_id_sha256": ident["doc_id_sha256"],
                    "relation_to_current": "anterieure_a_l_exemplaire_detenu",
                    "governing_edition": previous_edition,
                    "missing_evidence": None,
                })
                print(f"  {key}: {ident['filename']} porte l'edition "
                      f"{ident['edition']}, ANTERIEURE a l'exemplaire detenu "
                      f"({previous_edition}). Conservee comme copie, l'entree "
                      "n'est pas modifiee.")
                held_alongside.append(f"{ident['reference']} ed. {ident['edition']}")
                continue
            if prev_year == ident["edition_year"]:
                # Meme edition, fichier different: une empreinte de plus, pas
                # une edition de plus.
                entry.setdefault("alternate_copy_hashes", []).append(previous_digest)
            else:
                _older_copy(entry["reference"], previous_edition, previous_digest)
        for o in older:
            _older_copy(o["reference"], o["edition"], o["doc_id_sha256"])

        entry.update({
            "reference": ident["reference"],
            "edition_read_from_cover": f"{ident['edition']} (PARSEE en page 1)",
            "effective_from": ident["effective_from"],
            "status": ("acquired" if entry.get("status") == "acquired"
                       else "acquired_for_reading"),
            "doc_id_sha256": ident["doc_id_sha256"],
        })
        acq["notes"] = (
            (previous_note + "\n\n--- exemplaire NBN depose ---\n"
             if previous_note else "")
            + f"Identite PARSEE en page 1 de {ident['filename']}. "
            + (f"Indice de classement NBN: {ident['indice']}. "
               if ident.get("indice") else "")
            + f"Edition {ident['edition']}, en vigueur depuis "
            + f"{ident['effective_from'] or 'date non lue'}. "
            + (
                f"CETTE EDITION REMPLACE {', '.join(closed)} — exemplaire(s) "
                "PERIME(S), clos par effective_to; empreintes conservees dans "
                "superseded_copies, une etude signee sous l'ancienne edition "
                "devant rester lisible dix ans. "
                if closed else ""
            )
            + (
                f"DEUX EDITIONS DETENUES: {', '.join(held_alongside)} a cote de "
                f"celle-ci. Laquelle fait foi est pending_verification — voir "
                "concurrent_copies[].missing_evidence. Aucune valeur ne doit "
                "etre confirmee depuis l'une ou l'autre avant que la question "
                "soit tranchee sur piece. "
                if held_alongside else ""
            )
            + (
                f"Le document declare remplacer {', '.join(ident['replaces'])}. "
                if ident["replaces"] and not closed and not held_alongside else ""
            )
            + "STATUT A DECLARER par l'ingenieur qui depose."
        )
        recorded.append(
            f"{key:18s} {ident['reference']:24s} ed.{ident['edition']} "
            f"{ident['effective_from'] or '?':12s} {ident['doc_id_sha256'][:12]}"
        )

    mirrored = _mirror_to_other_countries(data)

    if not args.dry_run:
        CATALOGUE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print(f"\n{len(recorded)} annexe(s) belge(s) enregistree(s):")
    for line in recorded:
        print("   " + line)
    if superseded:
        print(f"\n*** {len(superseded)} EDITION(S) DETENUE(S) DEVENUE(S) PERIMEE(S) ***")
        for line in superseded:
            print("   " + line)
        print("   Closes par effective_to, empreintes conservees. Une etude")
        print("   signee sous l'ancienne edition reste lisible.")
    if announced:
        print(f"\n*** {len(announced)} ENTREE(S) A DEUX EDITIONS, "
              "SANS SUCCESSION ETABLIE ***")
        for line in announced:
            print("   " + line)
        print("   « Remplacera » est un futur: le NBN a publie, l'homologation")
        print("   au Moniteur belge n'est pas lue. Clore l'ancienne edition")
        print("   reviendrait a dater un arrete royal que personne n'a vu.")
    if duplicates:
        print(f"\n{len(duplicates)} doublon(s) exact(s) ignore(s) sans consequence:")
        for line in duplicates:
            print("   " + line)
    if created:
        print(f"\n{len(created)} entree(s) creee(s): "
              f"{', '.join(sorted(created))}")
    if mirrored:
        print(f"{len(mirrored)} entree(s) miroir FR/ES/DE.")
    if skipped:
        print(f"\n{len(skipped)} fichier(s) ignore(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
