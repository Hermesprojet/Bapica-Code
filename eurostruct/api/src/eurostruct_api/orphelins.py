"""Proposer la suppression d'objets orphelins — sans jamais supprimer.

CE QUE CE MODULE FAIT, ET CE QU'IL NE PEUT PAS FAIRE
------------------------------------------------------
`reconciliation.py` constate: telle cle du magasin n'est referencee par aucune
ligne. Ce module transforme ce constat en **proposition**, et s'arrete la. Il
n'a aucun code de suppression, aucune dependance capable d'ecrire dans le
magasin, et aucun mode qui ne soit pas `dry-run`. Le seul artefact qu'il
produit est un manifeste.

POURQUOI LA SUPPRESSION AUTOMATIQUE EST EXCLUE
------------------------------------------------
Un objet orphelin ressemble a un dechet. Il peut aussi etre:

* un livrable dont la ligne n'a pas encore ete ecrite — la fenetre entre le
  depot et l'enregistrement est courte, elle n'est pas nulle;
* le seul exemplaire d'une piece dont la ligne a ete perdue par un incident
  qu'on n'a pas encore diagnostique;
* un objet ecrit par un autre service qui partage le seau.

Dans les trois cas, la suppression est irreversible et la piece a une valeur
de preuve sur DIX ANS (responsabilite decennale). Le cout d'un objet conserve
a tort est un peu d'espace disque. Le cout d'un objet supprime a tort est un
document qu'on ne peut plus produire devant un tribunal. Les deux erreurs ne
se valent pas, et le produit choisit toujours la premiere.

LES TROIS CONDITIONS D'UNE CANDIDATURE
----------------------------------------
1. **DEUX SCANS SEPARES.** Un objet vu orphelin une seule fois ne prouve rien:
   il peut avoir ete depose une seconde avant le scan. Il faut deux constats,
   et le second doit etre separe du premier d'au moins `DELAI_MINIMAL`
   (24 heures par defaut) — assez pour qu'une transaction interrompue, une
   reprise ou un deploiement soient termines.
2. **UN AGE DE GRACE.** L'objet lui-meme doit dater d'au moins
   `GRACE_PAR_DEFAUT` (30 jours). Un objet ecrit ce matin n'est pas un dechet,
   quoi qu'en dise un scan.
3. **AUCUNE LIGNE, DANS LES DEUX SCANS.** Si la cle est redevenue referencee
   entre les deux, la candidature tombe — et le journal en garde la trace.

LE JOURNAL EST FOURNI, PAS ECRIT ICI
--------------------------------------
Les scans anterieurs arrivent en argument. Ce module ne lit ni n'ecrit aucun
fichier de son propre chef: c'est l'operateur qui conserve le journal, en
append-only, la ou l'application n'ecrit pas. Un module qui tiendrait lui-meme
la memoire de ses scans pourrait la reecrire, et « vu deux fois » cesserait
d'etre une preuve.

CE QU'IL FAUDRA, ET QUI N'EST PAS ICI
---------------------------------------
L'outil de maintenance qui execute reellement une suppression est un
programme SEPARE, hors de l'API applicative, exigeant un double controle
operateur. Son contrat: n'accepter qu'un manifeste produit ici, en verifier
l'empreinte, refuser tout objet dont l'empreinte ou la taille a change depuis
la proposition, et journaliser chaque suppression avec les deux identites qui
l'ont autorisee. **Il n'existe pas.** Aucune ligne de ce depot ne supprime
d'objet, et l'identite applicative ne doit porter aucun droit de suppression
sur le seau (voir `docs/STOCKAGE.md` §5).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta

__all__ = [
    "DELAI_MINIMAL",
    "GRACE_PAR_DEFAUT",
    "Candidat",
    "Manifeste",
    "Observation",
    "proposer",
]

#: Ecart minimal entre les deux scans qui fondent une candidature.
DELAI_MINIMAL = timedelta(hours=24)

#: Age minimal de l'objet lui-meme.
GRACE_PAR_DEFAUT = timedelta(days=30)

#: Version du format du manifeste. Un outil de maintenance qui ne la connait
#: pas doit REFUSER le manifeste, pas l'interpreter au mieux.
FORMAT = "eurostruct/orphan-proposal"
VERSION = 1


@dataclass(frozen=True)
class Observation:
    """Un objet vu orphelin lors d'un scan, avec ce qui l'identifiait alors.

    L'EMPREINTE ET LA TAILLE VOYAGENT AVEC LA CLE. Deux scans qui verraient la
    meme cle porter des octets differents ne parlent pas du meme objet, et une
    proposition fondee sur cette confusion supprimerait le second en croyant
    supprimer le premier.
    """

    backend: str
    cle: str
    taille: int
    empreinte: str | None
    #: Date d'ecriture de l'objet, telle que le magasin la rapporte.
    ecrit_le: datetime
    #: Date du scan qui a fait ce constat.
    vu_le: datetime


@dataclass(frozen=True)
class Candidat:
    """Un objet qui remplit les trois conditions. Une PROPOSITION, rien de plus."""

    backend: str
    cle: str
    taille: int
    empreinte: str | None
    ecrit_le: str
    premiere_detection: str
    derniere_detection: str
    scans: int
    raison: str

    def en_dict(self) -> dict[str, object]:
        return {
            "backend": self.backend,
            "key": self.cle,
            "size_bytes": self.taille,
            "sha256": self.empreinte,
            "written_at": self.ecrit_le,
            "first_seen_at": self.premiere_detection,
            "last_seen_at": self.derniere_detection,
            "scan_count": self.scans,
            "reason": self.raison,
        }


@dataclass(frozen=True)
class Manifeste:
    """La proposition complete, et pourquoi chaque objet ecarte l'a ete.

    LES ECARTES SONT NOMMES, EUX AUSSI. Un manifeste qui ne montrerait que ses
    candidats ne permettrait pas de distinguer « rien ne remplit les
    conditions » de « le scan n'a rien vu ».
    """

    candidats: tuple[Candidat, ...]
    ecartes: tuple[dict[str, object], ...]
    pris_a: str
    delai_minimal_heures: float
    grace_jours: float
    mode: str = "dry-run"
    format: str = FORMAT
    version: int = VERSION
    #: Toujours vrai. Ecrit dans le manifeste pour que l'outil de maintenance
    #: n'ait pas a le supposer.
    aucune_suppression_effectuee: bool = field(default=True, init=False)

    def en_dict(self) -> dict[str, object]:
        return {
            "format": self.format,
            "version": self.version,
            "mode": self.mode,
            "no_deletion_performed": self.aucune_suppression_effectuee,
            "taken_at": self.pris_a,
            "policy": {
                "minimum_interval_hours": self.delai_minimal_heures,
                "grace_period_days": self.grace_jours,
                "required_scans": 2,
            },
            "candidates": [c.en_dict() for c in self.candidats],
            "excluded": list(self.ecartes),
            "notice": (
                "PROPOSITION SEULEMENT. Aucun objet n'a ete supprime, et ce "
                "programme n'en est pas capable. Toute suppression releve d'un "
                "outil de maintenance distinct, sous double controle operateur."
            ),
        }

    def en_json(self) -> str:
        """Le manifeste, sous une forme stable — donc dont l'empreinte a un sens."""
        return json.dumps(self.en_dict(), ensure_ascii=False, indent=2,
                          sort_keys=True)

    def empreinte(self) -> str:
        """L'empreinte du manifeste lui-meme.

        ELLE EST CE QUE L'OUTIL DE MAINTENANCE DEVRA EXIGER. Un manifeste
        transmis puis retouche — une cle ajoutee a la main — ne doit pas passer
        pour la proposition qui a ete relue.
        """
        return hashlib.sha256(self.en_json().encode("utf-8")).hexdigest()


def _iso(quand: datetime) -> str:
    return quand.replace(microsecond=0).isoformat()


def proposer(
    scans: list[list[Observation]],
    *,
    maintenant: datetime,
    delai_minimal: timedelta = DELAI_MINIMAL,
    grace: timedelta = GRACE_PAR_DEFAUT,
) -> Manifeste:
    """Construit la proposition. NE SUPPRIME RIEN, ET NE SAIT PAS SUPPRIMER.

    :param scans: les scans, du plus ancien au plus recent. Chacun est la liste
        des objets vus orphelins lors de ce scan. Il en faut au moins deux.
    :param maintenant: l'instant de reference, fourni et jamais lu de l'horloge
        — un manifeste doit pouvoir se rejouer a l'identique.
    """
    ecartes: list[dict[str, object]] = []
    if len(scans) < 2:
        return Manifeste(
            candidats=(),
            ecartes=({
                "reason": "moins de deux scans fournis",
                "scans": len(scans),
            },),
            pris_a=_iso(maintenant),
            delai_minimal_heures=delai_minimal.total_seconds() / 3600.0,
            grace_jours=grace.total_seconds() / 86400.0,
        )

    premier, dernier = scans[0], scans[-1]
    # LA CLE SEULE NE SUFFIT PAS A IDENTIFIER UN OBJET: on apparie sur la cle
    # ET l'empreinte, pour qu'un objet remplace entre deux scans ne soit pas
    # propose a la place de celui qui a ete constate.
    vus_au_premier = {(o.backend, o.cle): o for o in premier}

    candidats: list[Candidat] = []
    for observation in dernier:
        identite = (observation.backend, observation.cle)
        ancienne = vus_au_premier.get(identite)
        if ancienne is None:
            ecartes.append({
                "backend": observation.backend, "key": observation.cle,
                "reason": "vu une seule fois: un scan ne prouve pas un orphelin",
            })
            continue
        if ancienne.empreinte != observation.empreinte:
            ecartes.append({
                "backend": observation.backend, "key": observation.cle,
                "reason": ("les octets ont change entre les deux scans: ce "
                           "n'est pas le meme objet"),
            })
            continue
        ecart = observation.vu_le - ancienne.vu_le
        if ecart < delai_minimal:
            ecartes.append({
                "backend": observation.backend, "key": observation.cle,
                "reason": (f"scans trop rapproches: {ecart} < {delai_minimal}"),
            })
            continue
        age = maintenant - observation.ecrit_le
        if age < grace:
            ecartes.append({
                "backend": observation.backend, "key": observation.cle,
                "reason": f"age de grace non atteint: {age} < {grace}",
            })
            continue
        candidats.append(Candidat(
            backend=observation.backend,
            cle=observation.cle,
            taille=observation.taille,
            empreinte=observation.empreinte,
            ecrit_le=_iso(observation.ecrit_le),
            premiere_detection=_iso(ancienne.vu_le),
            derniere_detection=_iso(observation.vu_le),
            scans=2,
            raison=("aucune ligne de livrable ne reference cette cle, "
                    "constate lors de deux scans separes"),
        ))

    # LES CLES DISPARUES DU DERNIER SCAN SONT NOMMEES AUSSI. Une candidature
    # qui tombe parce que la ligne est reapparue est une information: elle dit
    # que la fenetre entre depot et enregistrement etait en cause.
    dans_dernier = {(o.backend, o.cle) for o in dernier}
    for identite, ancienne in vus_au_premier.items():
        if identite not in dans_dernier:
            ecartes.append({
                "backend": ancienne.backend, "key": ancienne.cle,
                "reason": ("n'est plus orphelin au dernier scan: une ligne le "
                           "reference desormais"),
            })

    ordre = sorted(candidats, key=lambda c: (c.backend, c.cle))
    return Manifeste(
        candidats=tuple(ordre),
        ecartes=tuple(sorted(ecartes, key=lambda e: (str(e.get("backend", "")),
                                                     str(e.get("key", ""))))),
        pris_a=_iso(maintenant),
        delai_minimal_heures=delai_minimal.total_seconds() / 3600.0,
        grace_jours=grace.total_seconds() / 86400.0,
    )
