#!/usr/bin/env python3
"""Deux defauts de composition du SQL par le shell, dans les harnais.

DEFAUT 1 — L'HEREDOC NON QUOTE QUI CONTIENT UNE SUBSTITUTION
-------------------------------------------------------------
Un heredoc ouvert par ``<<SQL`` — et non ``<<'SQL'`` — subit l'expansion du
shell. Ce qui ressemble a de la prose SQL est alors du shell. Mesure du 28/08 :

    montrer <<SQL
    -- voir `whoami` pour le detail
    SQL

fait parvenir a ``psql`` la ligne ``-- voir root pour le detail``. La
substitution s'execute, et sa sortie entre dans le flux SQL. Quatre harnais
d'autorite contenaient cette forme.

Une substitution ECHAPPEE (``\\`` ou ``\\$(``) n'est pas ce defaut : c'est la
forme correcte quand on ECRIT un script par heredoc — ``deploy_recovery.sh``
compose un faux ``psql`` dont le corps doit s'evaluer a l'execution, pas a
l'ecriture. Les compter aurait fait rougir la bonne pratique.

DEFAUT 2 — LA VALEUR LUE DANS LA BASE, RECOLLEE DANS UN LITTERAL SQL
---------------------------------------------------------------------
C'est le defaut le plus repandu, et le scanner ne le voyait pas : il ne
regardait QUE les heredocs, alors que sa forme dominante est ``-c``.

    MANIFESTE=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
    SORTIE=$(ctl   -tAc "select normative_finalize_deployment('$MANIFESTE')")

La valeur ne vient pas du harnais : elle vient de la base. Et le ``2>&1`` la
rend PIRE — en cas d'echec la variable contient un message d'erreur francais,
plein d'apostrophes. Mesure du 29/08, PostgreSQL 16.13 :

    VAL="ERROR:  le plan « x » n'est pas separe"
    insert into trace values ('$VAL');
    -> ERROR:  syntax error at or near "est"        (0 ligne inseree)

    psql -v m="$VAL" ... ; insert into trace values (:'m');
    -> 1 ligne, RECU: ERROR:  le plan « x » n'est pas separe

Le harnais ne mesure alors plus ce qu'il annonce : il lit un refus la ou il y
a une erreur de syntaxe. C'est exactement la faute qui a produit les onze
survivants de la campagne `3d0acc2` — un diagnostic sans rapport avec la cause.

La forme sure est la variable psql, ``-v m="$VAL"`` puis ``:'m'``. psql cite
la valeur lui-meme. Mesure : psql N'INTERPOLE PAS ``:nom`` dans un litteral
simple deja ecrit (``select 'avant :nom apres'`` rend ``avant :nom apres``),
donc la conversion ne peut pas deranger les corps existants.

POURQUOI LA CONVERSION N'EST PAS MECANIQUE — ET N'A PAS ETE FAITE
------------------------------------------------------------------
J'ai converti les trente-deux sites, puis j'ai tout repris. La raison est une
mesure que j'aurais du faire AVANT, et le defaut de raisonnement est exactement
celui que ce fichier denonce : j'avais prouve ``:'m'`` avec un HEREDOC, puis
generalise a ``-c``, que je n'avais jamais eprouve.

Mesure du 29/08, PostgreSQL 16.13 :

    psql -tA -v v="abc'def" -c "select :'v'"   -> ERROR: syntax error at ":"
    psql -tA -v v="abc'def"    <<<"select :'v'" -> abc'def

**psql n'interpole pas ses variables dans une chaine ``-c``.** Seules
l'entree standard et ``-f`` passent par l'analyseur qui les substitue. Vingt-
sept des trente-deux sites sont des ``-c`` : la conversion les a tous casses,
et `run.sh` l'a montre en trois surfaces rouges.

Passer ces sites a l'entree standard change leur semantique, et la mesure le
dit :

    psql -tAc "select 1/0"                        -> rc=1
    psql -tA        <<<"select 1/0"               -> rc=0   (!)
    psql -tA -v ON_ERROR_STOP=1 <<<"select 1/0"   -> rc=3

Sans ``ON_ERROR_STOP``, une erreur SQL rend ZERO : la conversion aurait rendu
VERTS des controles qui doivent etre rouges. Avec, le code passe de 1 a 3.
C'est un changement de semantique sur vingt-sept sites, dans quinze harnais,
qu'aucune execution disponible dans ce lot ne pouvait valider. Il n'est pas
fait ici.

LE CLIQUET
-----------
Le plafond vaut donc le compte MESURE, 31, et il ne peut que baisser :

  * un site de plus  -> rouge (la dette augmente) ;
  * un site de moins -> rouge aussi, avec la valeur a inscrire (un plafond
    perime ne mesure plus rien).

Ce n'est pas une exemption : le defaut reste nomme, compte, et sa reduction
verifiee. Le compte vaut 31 et non 32 parce que ``$mb``, dans la course D2 de
``authority_closure.sh``, est un PARAMETRE de fonction et non une variable
affectee depuis la base — la valeur qu'il porte vient pourtant bien de la base,
par ``$ma``. Ce que le scanner ne voit pas est ecrit ici plutot que suppose.

Rend 0 si rien n'est trouve, 1 sinon, 2 s'il n'a rien regarde.
"""
from __future__ import annotations

import pathlib
import re
import sys

OUVERTURE = re.compile(r"<<(-?)([A-Za-z_]\w*)\s*$")

#: Fonctions dont la valeur de retour vient de la base, jamais du harnais.
#: Recoller l'une d'elles dans un litteral SQL est le defaut 2.
LUES_DANS_LA_BASE = (
    "normative_settings_manifest",
    "normative_authority_manifest",
)

#: Dette MESUREE le 29/08 sur `db/test`. NE PEUT QUE BAISSER.
PLAFOND_RECOLLAGE = 31


def _corps_heredocs(lignes: list[str]):
    """Rend (ligne_ouverture, delimiteur, texte) pour chaque heredoc."""
    i = 0
    while i < len(lignes):
        m = OUVERTURE.search(lignes[i])
        if not m:
            i += 1
            continue
        delim = m.group(2)
        j, corps = i + 1, []
        while j < len(lignes) and lignes[j].strip() != delim:
            corps.append(lignes[j])
            j += 1
        yield i + 1, delim, "\n".join(corps)
        i = j + 1


def heredocs_a_risque(chemin: pathlib.Path) -> list[tuple[int, str]]:
    """Defaut 1 : heredoc non quote portant une substitution non echappee."""
    lignes = chemin.read_text(encoding="utf-8", errors="replace").split("\n")
    trouves: list[tuple[int, str]] = []
    for ligne, delim, texte in _corps_heredocs(lignes):
        if re.search(r"(?<!\\)`", texte) or re.search(r"(?<!\\)\$\(", texte):
            trouves.append((ligne, delim))
    return trouves


def _variables_lues_dans_la_base(lignes: list[str]) -> set[str]:
    """Les variables shell affectees depuis un appel a une fonction de la base.

    On ne devine pas : on releve `X=$(... normative_settings_manifest() ...)`
    et `X=$(...)` sur plusieurs lignes n'est pas couvert — c'est dit dans le
    rapport plutot que suppose silencieusement.
    """
    noms: set[str] = set()
    motif = re.compile(r"\b([A-Za-z_]\w*)=\$\(")
    for ligne in lignes:
        if not any(f in ligne for f in LUES_DANS_LA_BASE):
            continue
        m = motif.search(ligne)
        if m:
            noms.add(m.group(1))
    return noms


def recollages(chemin: pathlib.Path) -> list[tuple[int, str]]:
    """Defaut 2 : une de ces variables recollee dans un litteral SQL `'...'`.

    Vu partout, heredoc ou `-c` : on cherche la sequence `'$NOM'`, qui est le
    recollage lui-meme, quel que soit le vehicule.
    """
    lignes = chemin.read_text(encoding="utf-8", errors="replace").split("\n")
    noms = _variables_lues_dans_la_base(lignes)
    if not noms:
        return []
    motif = re.compile(r"'\$\{?(" + "|".join(map(re.escape, sorted(noms))) + r")\}?'")
    trouves: list[tuple[int, str]] = []
    for n, ligne in enumerate(lignes, 1):
        for m in motif.finditer(ligne):
            # L'AFFECTATION ELLE-MEME N'EST PAS UN RECOLLAGE.
            if re.search(r"\b[A-Za-z_]\w*=\$\(", ligne[:m.start()]) and \
               all(f not in ligne for f in LUES_DANS_LA_BASE):
                pass
            trouves.append((n, m.group(1)))
    return trouves


def fichiers_a_inspecter(racines: list[pathlib.Path]) -> list[pathlib.Path]:
    """UN CHEMIN DE FICHIER EST ACCEPTE.

    `glob` sur un fichier ne rend RIEN : le scanner inspectait zero fichier et
    annoncait « rien trouve ». Meme faute que la barriere AST, meme correction.
    """
    fichiers: list[pathlib.Path] = []
    for racine in racines:
        if racine.is_file():
            fichiers.append(racine)
        else:
            fichiers.extend(sorted(racine.glob("*.sh")))
    return fichiers


def main(argv: list[str]) -> int:
    racines = [pathlib.Path(a) for a in argv[1:]] or [pathlib.Path(".")]
    fichiers = fichiers_a_inspecter(racines)
    if not fichiers:
        print("REFUS: aucun fichier .sh a inspecter — un controle qui ne "
              "regarde rien ne vaut pas un controle reussi.", file=sys.stderr)
        return 2

    total_h = 0
    for f in fichiers:
        for ligne, delim in heredocs_a_risque(f):
            print(f"{f.name}:{ligne} (<<{delim}) substitution dans un heredoc "
                  f"non quote")
            total_h += 1

    sites: list[tuple[str, int, str]] = []
    for f in fichiers:
        for ligne, nom in recollages(f):
            sites.append((f.name, ligne, nom))

    n = len(sites)

    def lister() -> None:
        """Les sites ne sont listes QUE si le verdict est rouge: trente et une
        lignes a chaque execution verte seraient du bruit, et le bruit finit
        par etre saute."""
        for nom, ligne, v in sites:
            print(f"    {nom}:{ligne}  ${v}", file=sys.stderr)

    # LE PLAFOND EST UN INVARIANT DE CORPUS, PAS DE FICHIER.
    #
    # Applique par fichier, il rendait ROUGE tout cas fabrique — zero
    # recollage y est LU comme « plafond perime ». Les selftests l'ont montre
    # aussitot: quatre cas conformes declares en faute. Un fichier nomme se
    # juge donc sur ce qu'il contient (aucun recollage), un repertoire sur
    # l'ecart au plafond.
    corpus = all(r.is_dir() for r in racines)
    if corpus:
        if n > PLAFOND_RECOLLAGE:
            print(f"REFUS: {n} recollage(s), plafond {PLAFOND_RECOLLAGE}. Un "
                  f"nouveau site doit passer par l'entree standard et une "
                  f"variable psql — JAMAIS par -c, qui n'interpole pas.",
                  file=sys.stderr)
            lister()
        elif n < PLAFOND_RECOLLAGE:
            print(f"REFUS: {n} recollage(s) alors que le plafond en annonce "
                  f"{PLAFOND_RECOLLAGE}. Un plafond perime ne mesure plus "
                  f"rien : inscrire PLAFOND_RECOLLAGE = {n}.", file=sys.stderr)
            lister()
        conforme = n == PLAFOND_RECOLLAGE
        resume = f"{n} recollage(s) connu(s) au plafond"
    else:
        conforme = n == 0
        resume = f"{n} recollage(s)"
        if not conforme:
            lister()

    if total_h == 0 and conforme:
        print(f"composition du SQL: {len(fichiers)} fichier(s), aucune "
              f"substitution en heredoc non quote, {resume}.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
