"""Loading and resolution of national parameters.

TICKET 1.2 — the engine loads the parameter set for the project's country and
reference date, and **refuses to guess** a missing National Annex.

TICKET 1.3 — before any calculation runs, :meth:`ParameterSet.preflight` checks
every parameter the module declares it needs and reports **all** blockers at
once, not just the first one encountered. A user should not have to fix one
parameter, re-run, and discover the next.

The JSON files under ``data/`` are the source of truth for the seed of the
``national_annex_parameters`` table. The database is authoritative at runtime;
these files are what gets loaded into it (``db/seed/generate_ndp_seed.py``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Final, Sequence

from ..exceptions import (
    ConditionalParameterNeedsContext,
    DeprecatedNationalParameter,
    NationalAnnexIncomplete,
    UnrepresentableNationalParameter,
    UnverifiedNationalParameter,
)
from ..traceability import Clause, Journal, Provenance
from ..units import Q_, Quantity
from .model import (
    CountryRegistry,
    NationalAnnex,
    NationalParameter,
    ParameterVariant,
    RegulatoryFramework,
    SourceType,
    ValidationStatus,
    ValueProvenance,
)

__all__ = [
    "BlockingParameter",
    "ParameterSet",
    "PreflightReport",
    "available_countries",
    "load_country_registry",
    "load_parameter_set",
]

_DATA_DIR: Final[Path] = Path(__file__).parent / "data"


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class BlockingParameter:
    """One reason a calculation cannot proceed."""

    key: str
    reason: str          # annex_missing | missing | pending_verification | deprecated
    detail: str
    standard: str
    parameter_name: str
    national_annex_reference: str | None = None
    clause: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "reason": self.reason,
            "detail": self.detail,
            "standard": self.standard,
            "parameter_name": self.parameter_name,
            "national_annex_reference": self.national_annex_reference,
            "clause": self.clause,
        }


@dataclass(frozen=True, slots=True)
class PreflightReport:
    """Result of checking every parameter a calculation needs, before running.

    Designed to be read by a person *and* parsed by CI: :meth:`to_dict` gives
    the machine form, :meth:`render` the human one.
    """

    country_code: str
    as_of: date
    strict: bool
    required: tuple[str, ...]
    blocking: tuple[BlockingParameter, ...]

    @property
    def ok(self) -> bool:
        return not self.blocking

    def to_dict(self) -> dict[str, Any]:
        return {
            "country_code": self.country_code,
            "as_of": self.as_of.isoformat(),
            "strict": self.strict,
            "ok": self.ok,
            "required": list(self.required),
            "blocking": [b.to_dict() for b in self.blocking],
        }

    def render(self) -> str:
        """Human-readable summary, one line per blocking parameter."""
        if self.ok:
            return (
                f"Prevol OK — {len(self.required)} parametre(s) national(aux) "
                f"disponible(s) pour {self.country_code} au {self.as_of.isoformat()}."
            )
        lines = [
            f"Calcul impossible pour {self.country_code} au {self.as_of.isoformat()}: "
            f"{len(self.blocking)} parametre(s) national(aux) bloquant(s) "
            f"sur {len(self.required)} requis.",
            "",
        ]
        by_reason: dict[str, list[BlockingParameter]] = {}
        for b in self.blocking:
            by_reason.setdefault(b.reason, []).append(b)

        labels = {
            "annex_missing": "Annexe Nationale absente du referentiel",
            "missing": "Parametre absent de l'Annexe Nationale chargee",
            "pending_verification": "Valeur non relevee dans l'annexe publiee",
            "deprecated": "Valeur obsolete, remplacee",
        }
        for reason in sorted(by_reason):
            lines.append(f"  [{reason}] {labels.get(reason, reason)}")
            for b in sorted(by_reason[reason], key=lambda x: x.key):
                ref = f" — {b.national_annex_reference}" if b.national_annex_reference else ""
                clause = f" ({b.clause})" if b.clause else ""
                lines.append(f"    - {b.key}{clause}{ref}")
            lines.append("")
        lines.append(
            "Action (validation NORMATIVE, niveau 1 sur 3): faire relever chaque "
            "valeur dans l'Annexe Nationale publiee, a la page citee, puis passer "
            "le parametre au statut 'confirmed' avec verified_by et verified_at. "
            "Le relecteur est un ingenieur du bureau d'etudes: aucun tiers "
            "exterieur n'est requis. Cette etape porte sur le referentiel du "
            "pays, pas sur le projet — elle se fait une fois et sert a toutes "
            "les etudes."
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parameter set
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ParameterSet:
    """The national parameters applicable to one project.

    Bound to a country, a region, and the project's reference date, so that a
    calculation is reproducible years later even after a newer edition of the
    annex has been published.
    """

    registry: CountryRegistry
    region: str | None
    as_of: date
    strict: bool = True

    # --- resolution -------------------------------------------------------
    def _split(self, key: str) -> tuple[str, str]:
        if ":" not in key:
            raise KeyError(
                f"cle de parametre invalide: '{key}'. "
                "Format attendu: 'EN 1992-1-1:alpha_cc'."
            )
        standard, name = key.split(":", 1)
        return standard, name

    def find(self, key: str) -> NationalParameter | None:
        """The parameter record in force for *key*, or ``None``."""
        standard, name = self._split(key)
        annex = self.registry.annex_for(standard, self.as_of)
        if annex is None:
            return None
        for p in annex.parameters:
            if p.parameter_name == name and p.is_in_force(self.as_of):
                return p
        return None

    def annex_for_key(self, key: str) -> NationalAnnex | None:
        standard, _ = self._split(key)
        return self.registry.annex_for(standard, self.as_of)

    # --- preflight (TICKET 1.3) ------------------------------------------
    def preflight(self, required: Sequence[str]) -> PreflightReport:
        """Check every parameter a calculation needs, reporting all blockers.

        Called before the calculation starts, so the user gets the complete
        list in one pass.
        """
        blocking: list[BlockingParameter] = []
        for key in required:
            standard, name = self._split(key)
            annex = self.registry.annex_for(standard, self.as_of)

            if annex is None:
                blocking.append(
                    BlockingParameter(
                        key=key,
                        reason="annex_missing",
                        detail=(
                            f"aucune Annexe Nationale {standard} en vigueur pour "
                            f"{self.registry.country_code} au {self.as_of.isoformat()}. "
                            "Le moteur ne substitue pas l'annexe d'un autre pays ni "
                            "d'une autre edition."
                        ),
                        standard=standard,
                        parameter_name=name,
                    )
                )
                continue

            p = self.find(key)
            if p is None:
                blocking.append(
                    BlockingParameter(
                        key=key,
                        reason="missing",
                        detail=(
                            f"le parametre '{name}' n'est pas renseigne dans "
                            f"{annex.reference} ({annex.edition}). Aucune valeur par "
                            "defaut n'est substituee."
                        ),
                        standard=standard,
                        parameter_name=name,
                        national_annex_reference=annex.reference,
                    )
                )
                continue

            if p.validation_status is ValidationStatus.DEPRECATED:
                blocking.append(
                    BlockingParameter(
                        key=key, reason="deprecated",
                        detail=p.notes or "valeur marquee obsolete",
                        standard=standard, parameter_name=name,
                        national_annex_reference=annex.reference, clause=p.clause,
                    )
                )
                continue

            if p.validation_status is ValidationStatus.NOT_REPRESENTABLE:
                blocking.append(
                    BlockingParameter(
                        key=key, reason="not_representable",
                        detail=(
                            p.notes
                            or "l'annexe fixe ce parametre sous une forme non scalaire"
                        ),
                        standard=standard, parameter_name=name,
                        national_annex_reference=annex.reference, clause=p.clause,
                    )
                )
                continue

            if self.strict and not p.usable_in_strict_mode:
                blocking.append(
                    BlockingParameter(
                        key=key, reason="pending_verification",
                        detail=(
                            f"valeur {p.parameter_value} {p.unit} non relevee dans "
                            f"{p.national_annex_reference}. Statut: "
                            f"{p.validation_status.value}."
                        ),
                        standard=standard, parameter_name=name,
                        national_annex_reference=annex.reference, clause=p.clause,
                    )
                )

        return PreflightReport(
            country_code=self.registry.country_code,
            as_of=self.as_of,
            strict=self.strict,
            required=tuple(required),
            blocking=tuple(blocking),
        )

    def require(self, required: Sequence[str]) -> None:
        """Preflight, raising :class:`NationalAnnexIncomplete` if anything blocks."""
        report = self.preflight(required)
        if not report.ok:
            raise NationalAnnexIncomplete(report)

    # --- access -----------------------------------------------------------
    def get(
        self,
        key: str,
        journal: Journal | None = None,
        *,
        condition: str | None = None,
    ) -> Quantity:
        """Fetch a parameter, recording its provenance in *journal*.

        Prefer calling :meth:`require` once up front: this method raises on the
        first problem it meets, which is the right behaviour for a single
        lookup but a poor experience as a discovery mechanism.

        :param condition: which verification is being performed, for parameters
            the National Annex branches. Mandatory for those, refused for the
            others — passing one where the annex defines no branch would look
            like the condition had been honoured when nothing checked it.
        """
        p = self.find(key)
        if p is None:
            annex = self.annex_for_key(key)
            standard, name = self._split(key)
            if annex is None:
                raise KeyError(
                    f"aucune Annexe Nationale {standard} en vigueur pour "
                    f"'{self.registry.country_code}' au {self.as_of.isoformat()}. "
                    "Le moteur ne devine pas une annexe absente."
                )
            raise KeyError(
                f"parametre '{name}' absent de {annex.reference} ({annex.edition}). "
                "Aucune valeur par defaut n'est substituee: renseigner ce parametre "
                "avant de calculer."
            )

        if p.validation_status is ValidationStatus.DEPRECATED:
            raise DeprecatedNationalParameter(key, p.notes)

        if p.validation_status is ValidationStatus.NOT_REPRESENTABLE:
            raise UnrepresentableNationalParameter(key, p.notes)

        if self.strict and not p.usable_in_strict_mode:
            raise UnverifiedNationalParameter(
                key, self.registry.country_code, p.validation_status.value
            )

        if p.is_conditional:
            if condition is None or condition not in p.conditions:
                raise ConditionalParameterNeedsContext(key, p.conditions, condition)
            value = p.value_for(condition)
        else:
            # Un cas fourni la ou l'annexe ne distingue pas n'est PAS une
            # erreur. Le module a raison d'annoncer la verification qu'il
            # effectue; que l'annexe branche ou non dessus la regarde, elle.
            # Refuser ici punissait l'appelant pour la forme de l'annexe: le
            # module d'effort tranchant, correct en declarant « other »,
            # echouait sur la France dont l'alpha_cc est un simple scalaire.
            # La valeur unique s'applique alors a tous les cas, y compris
            # celui-la, et le journal note que la distinction n'existe pas.
            value = p.parameter_value

        if value is None:  # pragma: no cover - guarded above
            raise UnrepresentableNationalParameter(key, p.notes)

        q = Q_(value, p.unit)
        if journal is not None and key not in journal._index:
            journal.input(
                symbol=key,
                description=p.description,
                value=q,
                provenance=Provenance.national_annex(
                    key, _provenance_detail(p) + _case_note(p, condition)
                ),
                clause=_clause_of(p),
            )
        return q

    # --- reporting --------------------------------------------------------
    def keys(self) -> tuple[str, ...]:
        out: list[str] = []
        for a in self.registry.annexes:
            if a.is_in_force(self.as_of):
                out.extend(p.key for p in a.parameters if p.is_in_force(self.as_of))
        return tuple(sorted(out))

    def unverified_keys(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                k for k in self.keys()
                if (p := self.find(k)) is not None and not p.usable_in_strict_mode
            )
        )

    def with_strict(self, strict: bool) -> "ParameterSet":
        return ParameterSet(self.registry, self.region, self.as_of, strict)

    def summary(self) -> dict[str, Any]:
        """What the note de calcul prints in 'referentiel applique'."""
        annexes = [a.to_dict() for a in self.registry.annexes if a.is_in_force(self.as_of)]
        params: dict[str, Any] = {}
        for k in self.keys():
            p = self.find(k)
            if p is not None:
                params[k] = p.to_dict()
        return {
            "country": self.registry.country_code,
            "country_name": self.registry.country_name,
            "region": self.region,
            "as_of": self.as_of.isoformat(),
            "strict": self.strict,
            "regulatory_framework": self.registry.regulatory_framework.to_dict(),
            "annexes": annexes,
            "unverified": list(self.unverified_keys()),
            "parameters": params,
        }


def _clause_of(p: NationalParameter) -> Clause:
    note = (
        f"{p.national_annex_reference} ed. {p.edition} "
        f"[{p.validation_status.value}]"
    )
    if p.en_recommended is not None and p.en_recommended != p.parameter_value:
        note += f" (valeur recommandee EN: {p.en_recommended})"
    return Clause(
        standard=p.standard, clause=p.clause, equation=None, national_note=note
    )


def _case_note(p: NationalParameter, condition: str | None) -> str:
    """What the journal says about the verification case that was declared.

    Three situations, and the note de calcul must distinguish them: a branch
    was chosen, a case was declared but this annex does not branch on it, or
    no case was in play at all.
    """
    if condition is None:
        return ""
    if p.is_conditional:
        return f" [cas: {condition}]"
    return f" [cas declare: {condition}; cette annexe ne distingue pas les cas]"


def _provenance_detail(p: NationalParameter) -> str:
    parts = [p.national_annex_reference, f"ed. {p.edition}", p.source_official]
    if p.source_url_or_doc_id:
        parts.append(p.source_url_or_doc_id)
    if p.verified_by:
        parts.append(f"releve par {p.verified_by} le {p.verified_at}")
    return " · ".join(x for x in parts if x)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def available_countries() -> list[str]:
    return sorted(p.stem.upper() for p in _DATA_DIR.glob("*.json"))


def _as_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


@lru_cache(maxsize=None)
def load_country_registry(country: str) -> CountryRegistry:
    """Load every National Annex known for *country*."""
    path = _DATA_DIR / f"{country.lower()}.json"
    if not path.exists():
        raise KeyError(
            f"aucun referentiel national pour le pays '{country}'. "
            f"Pays disponibles: {', '.join(available_countries()) or 'aucun'}."
        )
    raw = json.loads(path.read_text(encoding="utf-8"))

    annexes: list[NationalAnnex] = []
    for a in raw["annexes"]:
        eff_from = date.fromisoformat(a["effective_from"])
        eff_to = _as_date(a.get("effective_to"))
        params = tuple(
            NationalParameter(
                country_code=raw["country_code"],
                standard_family=a["standard_family"],
                part=a["part"],
                national_annex_reference=a["reference"],
                edition=a["edition"],
                effective_from=_as_date(item.get("effective_from")) or eff_from,
                effective_to=_as_date(item.get("effective_to")) or eff_to,
                parameter_name=name,
                parameter_value=(
                    None
                    if item.get("parameter_value") is None
                    else float(item["parameter_value"])
                ),
                unit=item.get("unit", "dimensionless"),
                source_official=item.get("source_official", a["source_official"]),
                source_url_or_doc_id=item.get(
                    "source_url_or_doc_id", a.get("source_url_or_doc_id")
                ),
                source_doc_id=item.get("source_doc_id"),
                source_page=item.get("source_page"),
                source_type=SourceType(item.get("source_type", "national_annex")),
                # Absent du JSON -> derive par __post_init__ depuis source_type.
                # Present -> il fait autorite, y compris quand il CONTREDIT
                # source_type: c'est tout l'interet du champ (cf. w_max).
                value_provenance=(
                    ValueProvenance(item["value_provenance"])
                    if item.get("value_provenance") else None
                ),
                validation_status=ValidationStatus(item["validation_status"]),
                verified_at=item.get("verified_at"),
                verified_by=item.get("verified_by"),
                notes=item.get("notes"),
                clause=item["clause"],
                description=item["description"],
                en_recommended=item.get("en_recommended"),
                variants=tuple(
                    ParameterVariant(
                        condition=v["condition"], value=float(v["value"]),
                        description=v["description"],
                    )
                    for v in item.get("variants", [])
                ),
            )
            for name, item in sorted(a["parameters"].items())
        )
        annexes.append(
            NationalAnnex(
                country_code=raw["country_code"],
                standard_family=a["standard_family"],
                part=a["part"],
                reference=a["reference"],
                edition=a["edition"],
                effective_from=eff_from,
                effective_to=eff_to,
                source_official=a["source_official"],
                source_url_or_doc_id=a.get("source_url_or_doc_id"),
                parameters=params,
            )
        )

    rf = raw["regulatory_framework"]
    return CountryRegistry(
        country_code=raw["country_code"],
        country_name=raw["country_name"],
        regulatory_framework=RegulatoryFramework(
            binding_reference=rf["binding_reference"],
            eurocode_status=rf["eurocode_status"],
            verification_regime=rf["verification_regime"],
            notes=tuple(rf.get("notes", [])),
        ),
        annexes=tuple(annexes),
        regions=tuple(raw.get("regions", [])),
    )


def load_parameter_set(
    country: str,
    region: str | None = None,
    strict: bool = True,
    as_of: date | None = None,
) -> ParameterSet:
    """Load the parameters applicable to a project.

    :param country: ISO 3166-1 alpha-2 — ``BE``, ``FR``, ``ES``, ``DE``.
    :param region: sub-national region where it changes the parameters.
    :param strict: when True (the default), an unconfirmed value blocks.
    :param as_of: the project's reference date, used to select the edition of
        the annex in force. Defaults to today. Pin it explicitly on a real
        project so the calculation stays reproducible after a new edition is
        published.
    """
    return ParameterSet(
        registry=load_country_registry(country.upper()),
        region=region,
        as_of=as_of or date.today(),
        strict=strict,
    )
