"""Trois états différents, que le produit annonçait comme un seul.

CE QUE « 0 SUR 29 » NE DIT PAS
--------------------------------
Le compte que l'API rendait jusqu'ici vient des **fichiers du dépôt**. Il dit
combien de fiches y portent `confirmed`, et la réponse est zéro — par
construction, puisque le dépôt n'écrit jamais ce statut. Ce nombre ne bouge
donc jamais, quelle que soit l'instance, et il ne décrit **aucune** instance.

Un ingénieur devant son écran pose une autre question : « est-ce que JE peux
lancer CE calcul-là, sur CETTE base-là ? » Trois faits distincts y répondent,
et les confondre a produit deux malentendus symétriques : croire qu'un
référentiel transcrit est utilisable, et croire qu'une instance où deux
ingénieurs ont signé est restée à zéro.

LES TROIS ÉTATS
----------------
**1. Transcrit** — ce que les fichiers versionnés portent : une valeur, une
clause, un folio, une empreinte de document, une provenance. C'est du travail
documentaire, et il est fait ou il ne l'est pas. Il ne dépend d'aucune base et
ne change pas d'une instance à l'autre.

**2. Décidé en base** — les décisions nominatives écrites par le chemin
d'autorité : une proposition, une approbation par un **second** ingénieur, une
consommation. C'est propre à l'instance, et c'est la seule chose qui puisse
faire passer un paramètre de « lu » à « opposable ».

**3. Utilisable pour ce calcul** — l'intersection des deux, restreinte aux
paramètres que le calcul demandé réclame vraiment. C'est le seul des trois qui
décide si le bouton marche. Une instance peut avoir dix-huit paramètres
confirmés et refuser quand même : il en manque un que ce chapitre-là réclame.

Aucun des trois ne se déduit des autres, et c'est pour cela qu'ils sont rendus
séparément plutôt que résumés par un ratio.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Sequence

from .model import ValidationStatus
from .passerelle import evaluer_depuis_le_provider
from .registry import ParameterSet

__all__ = [
    "Couverture",
    "EtatDuParametre",
    "couverture_du_calcul",
]


@dataclass(frozen=True, slots=True)
class EtatDuParametre:
    """Où en est UN paramètre, sur les trois plans à la fois."""

    key: str
    #: Ce que le dépôt porte.
    transcrit: str
    value_provenance: str
    #: Ce que la base porte. `None` quand aucune base n'a été interrogée —
    #: ce qui n'est pas la même chose que « aucune décision ».
    decide_en_base: bool | None
    verificateurs: tuple[str, ...]
    #: Ce que le calcul peut utiliser. Faux tant que les deux premiers ne se
    #: rejoignent pas sur ce paramètre.
    utilisable: bool
    #: Le motif du refus, tel que la passerelle l'a formulé. Vide si utilisable.
    pourquoi: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "transcrit": self.transcrit,
            "value_provenance": self.value_provenance,
            "decide_en_base": self.decide_en_base,
            "verificateurs": list(self.verificateurs),
            "utilisable": self.utilisable,
            "pourquoi": self.pourquoi,
        }


@dataclass(frozen=True, slots=True)
class Couverture:
    """La couverture d'UN calcul, sur UNE instance, à UNE date."""

    country_code: str
    as_of: date
    #: Les paramètres que ce calcul réclame. Ils viennent des modules, jamais
    #: d'une liste recopiée: un module qui en ajoute un le fait apparaître ici.
    requis: tuple[str, ...]
    parametres: tuple[EtatDuParametre, ...]
    #: Qui a répondu sur les confirmations. `None` = personne n'a été
    #: interrogé, et c'est un fait à afficher, pas un zéro à additionner.
    provider_identity: str | None
    provider_is_fictional: bool | None

    @property
    def base_interrogee(self) -> bool:
        return self.provider_identity is not None

    @property
    def utilisables(self) -> int:
        return sum(1 for p in self.parametres if p.utilisable)

    @property
    def decides(self) -> int:
        return sum(1 for p in self.parametres if p.decide_en_base)

    @property
    def transcrits_nationalement(self) -> int:
        """Combien portent une valeur RELEVÉE dans l'annexe publiée.

        C'est le travail documentaire fait, et il se compte même sans base.
        """
        return sum(
            1 for p in self.parametres
            if p.value_provenance in ("national_annex", "composed_normative_rule")
        )

    @property
    def prêt(self) -> bool:
        return bool(self.requis) and self.utilisables == len(self.requis)

    def to_dict(self) -> dict[str, Any]:
        return {
            "country_code": self.country_code,
            "as_of": self.as_of.isoformat(),
            "requis": list(self.requis),
            "base_interrogee": self.base_interrogee,
            "provider_identity": self.provider_identity,
            "provider_is_fictional": self.provider_is_fictional,
            "transcrits_nationalement": self.transcrits_nationalement,
            "decides_en_base": self.decides,
            "utilisables": self.utilisables,
            "total_requis": len(self.requis),
            "pret": self.prêt,
            "parametres": [p.to_dict() for p in self.parametres],
        }


def _verificateurs(provider: Any, cle: str) -> tuple[str, ...]:
    """Qui a signé, pour cette règle, d'après la base.

    LES NOMS NE SONT PAS INVENTES ICI, et aucun n'est fabriqué quand il
    manque: une confirmation sans vérificateur nommé n'arrive pas au bout du
    chemin d'autorité, et si elle y arrivait, c'est ce vide-là qu'il faut voir.
    """
    try:
        confirmations = provider.confirmations_for(cle)
    except Exception:  # noqa: BLE001 — une base qui répond mal n'est pas zéro
        raise
    noms: list[str] = []
    for c in confirmations:
        nom = getattr(c, "verifier_name", None) or getattr(c, "verifier_id", "")
        if nom and nom not in noms:
            noms.append(str(nom))
    return tuple(noms)


def couverture_du_calcul(
    jeu: ParameterSet,
    requis: Sequence[str],
    *,
    provider: Any = None,
) -> Couverture:
    """Les trois états, paramètre par paramètre, pour le calcul demandé.

    ``provider`` à ``None`` n'est pas « rien n'est confirmé » : c'est
    « personne n'a été interrogé ». Les deux se distinguent dans le résultat,
    parce qu'ils appellent deux gestes différents — brancher une base, ou
    faire relire un paramètre.
    """
    etats: list[EtatDuParametre] = []
    for cle in sorted(requis):
        parametre = jeu.find(cle)
        if parametre is None:
            etats.append(EtatDuParametre(
                key=cle, transcrit="absent", value_provenance="",
                decide_en_base=None, verificateurs=(), utilisable=False,
                pourquoi=("aucun parametre de ce nom n'est en vigueur a la "
                          "date de reference"),
            ))
            continue

        if provider is None:
            # PAS DE BASE: le transcrit est connu, le reste ne l'est pas. On
            # ne remplit pas les deux autres colonnes avec des zeros.
            etats.append(EtatDuParametre(
                key=cle,
                transcrit=parametre.validation_status.value,
                value_provenance=parametre.value_provenance.value,
                decide_en_base=None,
                verificateurs=(),
                utilisable=False,
                pourquoi=("aucune source de confirmation n'a ete interrogee: "
                          "le mode strict refuse, faute de savoir ce qui est "
                          "confirme"),
            ))
            continue

        rapport = evaluer_depuis_le_provider(parametre, provider=provider)
        noms = _verificateurs(provider, cle)
        etats.append(EtatDuParametre(
            key=cle,
            transcrit=parametre.validation_status.value,
            value_provenance=parametre.value_provenance.value,
            decide_en_base=bool(noms),
            verificateurs=noms,
            utilisable=rapport.usable,
            pourquoi="" if rapport.usable else rapport.reason,
        ))

    return Couverture(
        country_code=jeu.registry.country_code,
        as_of=jeu.as_of,
        requis=tuple(sorted(requis)),
        parametres=tuple(etats),
        provider_identity=(None if provider is None
                           else getattr(provider, "provider_identity", None)),
        provider_is_fictional=(None if provider is None
                               else getattr(provider, "is_fictional", None)),
    )


def transcription_du_referentiel(jeu: ParameterSet) -> dict[str, int]:
    """Le compte du DEPOT, nomme pour ce qu'il est.

    Il reste utile: il dit ou en est le travail documentaire, pays par pays.
    Ce qu'il ne fait pas, c'est decrire une instance — et c'est pour avoir
    laisse croire le contraire qu'il porte desormais ce nom-la.
    """
    comptes = {statut.value: 0 for statut in ValidationStatus}
    total = 0
    for cle in jeu.keys():
        parametre = jeu.find(cle)
        if parametre is None:
            continue
        comptes[parametre.validation_status.value] += 1
        total += 1
    comptes["total"] = total
    return comptes
