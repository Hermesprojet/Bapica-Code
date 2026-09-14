"""Le rapprochement entre la base et le magasin — en lecture seule.

CE QUE `docs/STOCKAGE.md` §5 PROMETTAIT, ET QUI N'EXISTAIT PAS
---------------------------------------------------------------
La politique du magasin est « rien n'est jamais supprimé par le produit ».
Elle a une contrepartie qui n'était pas outillée : **personne ne pouvait dire
ce que contient le compartiment**. La documentation l'écrivait noir sur blanc
— « un rapprochement en lecture seule … il n'existe pas encore ». C'est ce
fichier.

LES QUATRE VERDICTS, ET POURQUOI ILS NE SE VALENT PAS
------------------------------------------------------
``intact``      la ligne et l'objet s'accordent.
``absent``      **le grave.** Une ligne promet un document que le magasin n'a
                pas. Le téléchargement rendra 503 ; la note de calcul d'un
                dossier est introuvable. C'est le seul verdict qui décrit une
                promesse rompue envers un client.
``divergent``   l'objet existe mais sa taille ou son empreinte ne sont pas
                celles enregistrées. La route de téléchargement le refuserait
                déjà — elle vérifie l'empreinte au fil de la lecture — donc ce
                verdict dit surtout qu'une corruption s'est installée, sans
                attendre qu'un utilisateur la découvre.
``orphelin``    un objet que plus aucune ligne ne nomme. Ce n'est **pas** une
                anomalie de service : personne n'attend ce document. C'est du
                gaspillage tracé, et le résidu prévu par la politique.

Un rapprochement qui rendrait un seul nombre mélangerait une promesse rompue
et quelques kilo-octets perdus. Ils ne se traitent pas de la même façon et ne
réveillent pas les mêmes personnes.

CE QUE CET OUTIL NE FAIT PAS, ET NE FERA PAS
----------------------------------------------
**Il ne supprime rien.** Il n'y a pas d'option ``--supprimer``, pas de mode
``--reparer``, et ``ClientS3`` n'a de toute façon aucune méthode de
suppression. Reprendre un orphelin se fait hors du produit, par une personne,
sur des clés nommées une à une, avec une décision écrite.

**Il n'écrit pas non plus dans la base.** Sa transaction est ouverte en
lecture seule par PostgreSQL lui-même (``default_transaction_read_only``) :
ce n'est pas une intention, c'est le serveur qui refuserait.

IL N'EST PAS UNE ROUTE DE L'API, ET C'EST DELIBERE
----------------------------------------------------
Le rapprochement traverse **toutes** les organisations : c'est un geste
d'exploitation, comme une sauvegarde, pas une fonction offerte à un locataire.
L'exposer par l'API demanderait d'élargir la surface SQL du backend
authentifié à une lecture transverse de ``deliverables`` — exactement ce que
la frontière des rôles interdit. Il se lance donc depuis l'exploitation, avec
un rôle qui n'est **pas** celui de l'API.

    EUROSTRUCT_RECONCILIATION_DSN=… python3 -m eurostruct_api.reconciliation

AUCUN SECRET NE SORT D'ICI. Le DSN vient de l'environnement — jamais d'un
argument, qui serait lisible dans ``ps`` — et n'est ni affiché, ni journalisé,
ni rendu dans un message d'erreur.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import Any

from .stockage import (
    MagasinLisible,
    ObjetIntrouvable,
    StockageIndisponible,
    stockage_configure,
)

__all__ = ["Constat", "Rapport", "main", "rapprocher"]

#: La variable qui porte le DSN. Elle est distincte de celle de l'API pour que
#: personne ne lance un rapprochement avec le login du service par megarde: ce
#: login n'a aucun privilege de table, et le refus serait obscur.
VARIABLE_DSN = "EUROSTRUCT_RECONCILIATION_DSN"

#: Les verdicts, du plus grave au plus benin. L'ordre est celui du rapport.
ABSENT = "absent"
DIVERGENT = "divergent"
ORPHELIN = "orphelin"
INTACT = "intact"


@dataclass(frozen=True)
class Constat:
    """Une observation, attribuee a une ligne ou a une cle."""

    verdict: str
    chemin: str
    org_id: str | None = None
    project_id: str | None = None
    deliverable_id: str | None = None
    detail: str = ""


@dataclass(frozen=True)
class Rapport:
    """Le resultat complet, denombre par verdict."""

    constats: tuple[Constat, ...]
    lignes_lues: int
    objets_lus: int
    empreintes_verifiees: bool

    def compte(self, verdict: str) -> int:
        return sum(1 for c in self.constats if c.verdict == verdict)

    @property
    def sain(self) -> bool:
        """Vrai si rien d'autre que des ``intact`` n'a ete constate."""
        return all(c.verdict == INTACT for c in self.constats)


# --------------------------------------------------------------------- base
def _lignes_de_livrables(connexion: Any) -> list[dict[str, Any]]:
    """Les livrables, tels que la base les enregistre.

    LA TRANSACTION EST EN LECTURE SEULE, ET C'EST POSTGRESQL QUI LE TIENT.
    ``set transaction read only`` fait refuser toute ecriture par le serveur,
    y compris une ecriture qu'un defaut de ce fichier tenterait. C'est la
    difference entre « cet outil ne veut pas ecrire » et « cet outil ne peut
    pas ecrire ».
    """
    with connexion.cursor() as curseur:
        curseur.execute("set transaction read only")
        curseur.execute(
            "select id::text, org_id::text, project_id::text, "
            "       storage_path, sha256, size_bytes, storage_backend "
            "  from deliverables "
            " order by org_id, project_id, storage_path"
        )
        colonnes = [d[0] for d in curseur.description]
        return [dict(zip(colonnes, r, strict=True)) for r in curseur.fetchall()]


# ------------------------------------------------------------ rapprochement
def rapprocher(lignes: list[dict[str, Any]], magasin: MagasinLisible, *,
               empreintes: bool = False) -> Rapport:
    """Compare les lignes aux objets. Ne modifie ni l'un ni l'autre.

    LES LIGNES D'UN AUTRE MAGASIN SONT ECARTEES, PAS DECLAREES ABSENTES. Un
    deploiement qui a migre du disque vers S3 garde des lignes portant
    ``storage_backend = 'local'`` ; les chercher dans le compartiment S3 les
    dirait toutes absentes et noierait les vraies. On ne rapproche que ce que
    le magasin configure est cense detenir.

    PLUSIEURS LIGNES PEUVENT PARTAGER UN OBJET, et c'est normal : les cles
    derivent du contenu, donc deux revisions au contenu identique ecrivent au
    meme endroit. Un objet n'est orphelin que si **aucune** ligne ne le nomme.
    """
    constats: list[Constat] = []
    attendus: dict[str, list[dict[str, Any]]] = {}

    for ligne in lignes:
        if ligne["storage_backend"] != magasin.nom:
            continue
        attendus.setdefault(ligne["storage_path"], []).append(ligne)

    presents = dict(magasin.enumerer())

    for chemin, concernees in sorted(attendus.items()):
        ligne = concernees[0]
        commun = {
            "chemin": chemin,
            "org_id": ligne["org_id"],
            "project_id": ligne["project_id"],
            "deliverable_id": ligne["id"],
        }
        taille = presents.get(chemin)
        if taille is None:
            constats.append(Constat(
                verdict=ABSENT, **commun,
                detail=("la ligne promet un document que le magasin n'a pas: "
                        "son telechargement rendra 503"),
            ))
            continue

        attendue = int(ligne["size_bytes"])
        if taille != attendue:
            constats.append(Constat(
                verdict=DIVERGENT, **commun,
                detail=f"taille {taille} octets, {attendue} enregistres",
            ))
            continue

        if empreintes:
            try:
                octets = magasin.lire(chemin)
            except (ObjetIntrouvable, StockageIndisponible) as cause:
                constats.append(Constat(
                    verdict=ABSENT, **commun,
                    detail=f"relecture impossible: {cause}",
                ))
                continue
            trouvee = hashlib.sha256(octets).hexdigest()
            if trouvee != ligne["sha256"]:
                constats.append(Constat(
                    verdict=DIVERGENT, **commun,
                    detail=("l'empreinte des octets presents n'est pas celle "
                            "enregistree"),
                ))
                continue

        constats.append(Constat(verdict=INTACT, **commun))

    for chemin in sorted(set(presents) - set(attendus)):
        constats.append(Constat(
            verdict=ORPHELIN, chemin=chemin,
            detail=("aucune ligne de `deliverables` ne nomme cet objet; il "
                    "n'est PAS supprime"),
        ))

    ordre = {ABSENT: 0, DIVERGENT: 1, ORPHELIN: 2, INTACT: 3}
    constats.sort(key=lambda c: (ordre[c.verdict], c.chemin))
    return Rapport(tuple(constats), len(lignes), len(presents), empreintes)


# ------------------------------------------------------------------ rendu
def rendre(rapport: Rapport, *, json_: bool, flux: Any) -> None:
    if json_:
        json.dump({
            "lignes_lues": rapport.lignes_lues,
            "objets_lus": rapport.objets_lus,
            "empreintes_verifiees": rapport.empreintes_verifiees,
            "comptes": {v: rapport.compte(v)
                        for v in (ABSENT, DIVERGENT, ORPHELIN, INTACT)},
            "constats": [asdict(c) for c in rapport.constats
                         if c.verdict != INTACT],
        }, flux, ensure_ascii=False, indent=2)
        flux.write("\n")
        return

    print("=" * 70, file=flux)
    print(" EUROSTRUCT — rapprochement base / magasin (LECTURE SEULE)",
          file=flux)
    print("=" * 70, file=flux)
    print(f" lignes lues : {rapport.lignes_lues}", file=flux)
    print(f" objets lus  : {rapport.objets_lus}", file=flux)
    print(f" empreintes  : {'verifiees' if rapport.empreintes_verifiees else 'non verifiees (--empreintes)'}",
          file=flux)
    print("-" * 70, file=flux)
    for verdict in (ABSENT, DIVERGENT, ORPHELIN, INTACT):
        print(f" {verdict:<12} {rapport.compte(verdict)}", file=flux)
    print("-" * 70, file=flux)

    for constat in rapport.constats:
        if constat.verdict == INTACT:
            continue
        print(f" [{constat.verdict}] {constat.chemin}", file=flux)
        print(f"     {constat.detail}", file=flux)

    print("=" * 70, file=flux)
    if rapport.sain:
        print(" VERDICT: la base et le magasin s'accordent.", file=flux)
    else:
        print(" VERDICT: ecarts constates. AUCUN N'A ETE CORRIGE — cet outil "
              "ne modifie rien.", file=flux)


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        prog="eurostruct-reconciliation",
        description=("Rapproche `deliverables` du magasin d'objets. "
                     "Ne modifie NI l'un NI l'autre."),
    )
    analyseur.add_argument(
        "--empreintes", action="store_true",
        help=("relit chaque objet et verifie son sha256. Sans cette option "
              "seule la taille est comparee, ce qui n'exige aucune lecture."))
    analyseur.add_argument("--json", action="store_true",
                           dest="json_", help="rapport lisible par machine")
    options = analyseur.parse_args(argv)

    dsn = os.environ.get(VARIABLE_DSN, "")
    if not dsn:
        print(f"REFUS: {VARIABLE_DSN} n'est pas defini.\n"
              "       Le rapprochement lit `deliverables` a travers TOUTES les "
              "organisations:\n"
              "       c'est un geste d'exploitation, et il exige un role qui "
              "peut le faire.\n"
              "       N'utilisez PAS le login du service applicatif: il n'a "
              "aucun privilege\n"
              "       de table, et son refus serait obscur.",
              file=sys.stderr)
        return 2

    # LE PILOTE EST CELUI DU PRODUIT — `psycopg2`, comme
    # `FabriqueConnexionPostgres`. En viser un autre ferait de cet outil un
    # binaire qui ne s'installe pas la ou le service tourne.
    try:
        import psycopg2
    except ImportError:
        print("REFUS: le pilote `psycopg2` n'est pas installe.",
              file=sys.stderr)
        return 2

    try:
        magasin = stockage_configure()
    except StockageIndisponible as cause:
        print(f"REFUS: magasin inutilisable: {cause}", file=sys.stderr)
        return 2

    # LA SESSION EST EN LECTURE SEULE DES L'ORIGINE. `set_session(readonly)`
    # vaut pour toutes les transactions de cette connexion; `set transaction
    # read only` dans `_lignes_de_livrables` le redit au niveau transactionnel,
    # pour que la garantie tienne aussi quand la connexion vient d'ailleurs.
    connexion = None
    try:
        connexion = psycopg2.connect(dsn)
        connexion.set_session(readonly=True)
        lignes = _lignes_de_livrables(connexion)
    except Exception as cause:  # noqa: BLE001
        # LE DSN N'APPARAIT PAS DANS CE MESSAGE. Il porte un mot de passe.
        print(f"REFUS: la base n'a pas repondu ({type(cause).__name__}).",
              file=sys.stderr)
        return 2
    finally:
        # `with psycopg2.connect(...)` NE FERME PAS la connexion — il ne fait
        # que valider ou annuler la transaction. Une fermeture explicite est
        # la seule facon de ne pas laisser filer un descripteur.
        if connexion is not None:
            connexion.close()

    rapport = rapprocher(lignes, magasin, empreintes=options.empreintes)
    rendre(rapport, json_=options.json_, flux=sys.stdout)
    return 0 if rapport.sain else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
