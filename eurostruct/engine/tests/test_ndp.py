"""National parameters — EPIC 1.

Defends interdictions 2, 3 and 4 of the cahier des charges: no invented value,
no Eurocode applied without its National Annex, and Spain not treated as a
pure-Eurocode country.
"""

from __future__ import annotations

from datetime import date

import pytest

from eurostruct_engine.basis import DesignSituation
from eurostruct_engine.ec2 import RectangularSection, design_flexure
from eurostruct_engine.ec2.beam_flexure import EC2_11, required_parameters
from eurostruct_engine.exceptions import (
    ConditionalParameterNeedsContext,
    DeprecatedNationalParameter,
    NationalAnnexIncomplete,
    UnrepresentableNationalParameter,
    UnverifiedNationalParameter,
)
from eurostruct_engine.materials import concrete, reinforcement
from eurostruct_engine.ndp import (
    ValidationStatus,
    available_countries,
    load_country_registry,
    load_parameter_set,
)
from eurostruct_engine.traceability import Journal
from eurostruct_engine.units import Q_

AS_OF = date(2026, 7, 26)
ALL_COUNTRIES = ("BE", "FR", "ES", "DE")


# ---------------------------------------------------------------------------
# TICKET 1.2 — registry per country / standard / part / version
# ---------------------------------------------------------------------------
def test_all_four_markets_are_present() -> None:
    assert set(available_countries()) == set(ALL_COUNTRIES)


def test_unknown_country_is_refused() -> None:
    with pytest.raises(KeyError, match="aucun referentiel national"):
        load_country_registry("XX")


@pytest.mark.parametrize("country", ALL_COUNTRIES)
def test_registry_carries_the_annex_identity(country: str) -> None:
    """TICKET 1.1: family, part, reference, edition and validity are separate."""
    reg = load_country_registry(country)
    annex = reg.annex_for("EN 1992-1-1", AS_OF)
    assert annex is not None
    assert annex.standard_family == "EN 1992"
    assert annex.part == "1-1"
    assert annex.reference
    assert annex.edition
    assert annex.source_official
    assert annex.effective_from <= AS_OF


@pytest.mark.parametrize("country", ALL_COUNTRIES)
def test_every_parameter_declares_source_status_and_clause(country: str) -> None:
    reg = load_country_registry(country)
    for annex in reg.annexes:
        for p in annex.parameters:
            assert p.parameter_name and p.clause and p.description
            assert p.source_official
            assert isinstance(p.validation_status, ValidationStatus)
            assert p.key.startswith(f"{p.standard}:")
            assert p.unit


def test_engine_refuses_to_guess_a_missing_annex() -> None:
    """TICKET 1.2, acceptance criterion 2: no substitution, no fallback."""
    p = load_parameter_set("BE", strict=False, as_of=AS_OF)
    with pytest.raises(KeyError, match="ne devine pas une annexe absente"):
        p.get("EN 1993-1-1:gamma_M0")          # steel annex not loaded
    report = p.preflight(["EN 1993-1-1:gamma_M0"])
    assert report.blocking[0].reason == "annex_missing"


def test_annex_not_yet_in_force_is_not_selected() -> None:
    """Resolution is by date: an annex is not used before it takes effect."""
    reg = load_country_registry("BE")
    annex = reg.annex_for("EN 1992-1-1", date(2000, 1, 1))
    assert annex is None


def test_parameter_set_is_pinned_to_a_reference_date() -> None:
    p = load_parameter_set("FR", strict=False, as_of=AS_OF)
    assert p.as_of == AS_OF
    assert p.summary()["as_of"] == "2026-07-26"


def test_invalid_key_format_is_rejected() -> None:
    p = load_parameter_set("BE", strict=False, as_of=AS_OF)
    with pytest.raises(KeyError, match="Format attendu"):
        p.get("alpha_cc")


# ---------------------------------------------------------------------------
# TICKET 1.3 — strict mode blocks, and reports every blocker at once
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("country", ALL_COUNTRIES)
def test_strict_mode_blocks_every_unverified_parameter(country: str) -> None:
    p = load_parameter_set(country, strict=True, as_of=AS_OF)
    required = required_parameters(DesignSituation.PERSISTENT)
    report = p.preflight(required)
    assert not report.ok
    # All of them, not just the first: that is the point of the preflight.
    assert len(report.blocking) == len(required)
    assert {b.reason for b in report.blocking} == {"pending_verification"}


def test_preflight_report_is_readable_and_machine_parsable() -> None:
    """Acceptance criterion: usable by a human and by CI."""
    p = load_parameter_set("BE", strict=True, as_of=AS_OF)
    report = p.preflight(required_parameters(DesignSituation.PERSISTENT))

    text = report.render()
    assert "Calcul impossible pour BE" in text
    assert "NBN EN 1992-1-1 ANB" in text
    # Le message doit dire de QUELLE des trois validations il s'agit, et que
    # le relecteur est un ingenieur du bureau d'etudes — pas un tiers.
    assert "NORMATIVE" in text
    assert "ingenieur du bureau d'etudes" in text
    assert "aucun tiers" in text.lower()
    for b in report.blocking:
        assert b.key in text

    data = report.to_dict()
    assert data["ok"] is False
    assert data["country_code"] == "BE"
    assert data["as_of"] == "2026-07-26"
    assert len(data["blocking"]) == len(report.blocking)
    assert set(data["blocking"][0]) >= {
        "key", "reason", "detail", "standard", "parameter_name"
    }


def test_calculation_is_blocked_before_it_starts() -> None:
    """The whole list comes back in one exception, not one failure at a time."""
    p = load_parameter_set("FR", strict=True, as_of=AS_OF)
    with pytest.raises(NationalAnnexIncomplete) as e:
        design_flexure(
            section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
            concrete=concrete("C30/37"), steel=reinforcement("B500B"),
            M_Ed=Q_(250, "kN*m"), params=p,
        )
    assert len(e.value.blocking) == 8
    assert e.value.to_dict()["ok"] is False
    assert "NF EN 1992-1-1/NA" in str(e.value)


def test_single_lookup_still_raises_in_strict_mode() -> None:
    p = load_parameter_set("BE", strict=True, as_of=AS_OF)
    with pytest.raises(UnverifiedNationalParameter):
        p.get(f"{EC2_11}:alpha_cc")


def test_non_strict_mode_allows_exploratory_work() -> None:
    p = load_parameter_set("BE", strict=False, as_of=AS_OF)
    assert p.preflight(required_parameters(DesignSituation.PERSISTENT)).ok
    # Valeur belge relevee dans l'ANB, non encore confirmee par un ingenieur.
    # alpha_cc est conditionnel: il faut dire quelle verification on fait.
    assert p.get(f"{EC2_11}:alpha_cc", condition="axial_and_bending").magnitude == 0.85
    assert p.get(f"{EC2_11}:alpha_cc", condition="other").magnitude == 1.0


def test_missing_parameter_is_never_defaulted() -> None:
    p = load_parameter_set("BE", strict=False, as_of=AS_OF)
    with pytest.raises(KeyError, match="Aucune valeur par defaut"):
        p.get(f"{EC2_11}:parametre_inexistant")
    assert p.preflight([f"{EC2_11}:parametre_inexistant"]).blocking[0].reason == "missing"


# ---------------------------------------------------------------------------
# Deprecated values are refused in every mode
# ---------------------------------------------------------------------------
def test_deprecated_value_is_refused_even_outside_strict_mode() -> None:
    """A deprecated value is known wrong, unlike a merely unverified one.

    Built by rebuilding the registry with one parameter marked deprecated,
    rather than by patching methods: the frozen dataclasses make that both
    easy and faithful to how a real superseded edition would look.
    """
    import dataclasses

    from eurostruct_engine.ndp.registry import ParameterSet

    base = load_parameter_set("BE", strict=False, as_of=AS_OF)
    annex = base.registry.annexes[0]
    patched_params = tuple(
        dataclasses.replace(
            prm,
            validation_status=ValidationStatus.DEPRECATED,
            notes="remplacee par l'edition suivante",
        )
        if prm.parameter_name == "alpha_cc" else prm
        for prm in annex.parameters
    )
    registry = dataclasses.replace(
        base.registry,
        annexes=(dataclasses.replace(annex, parameters=patched_params),),
    )
    ps = ParameterSet(registry=registry, region=None, as_of=AS_OF, strict=False)

    report = ps.preflight([f"{EC2_11}:alpha_cc"])
    assert report.blocking[0].reason == "deprecated"
    with pytest.raises(DeprecatedNationalParameter, match="obsolete"):
        ps.get(f"{EC2_11}:alpha_cc")


# ---------------------------------------------------------------------------
# A parameter the annex fixes as a formula has no value, in any mode
# ---------------------------------------------------------------------------
def test_belgian_cot_theta_max_carries_no_value() -> None:
    """NBN EN 1992-1-1 ANB §6.2.3(2) replaces the 2,5 bound with an expression.

    The EN recommendation is 2,5 and the annex explicitly does not adopt it.
    Storing 2,5 anyway would be interdiction 2: a value with no source.
    """
    reg = load_country_registry("BE")
    annex = reg.annex_for(EC2_11, AS_OF)
    assert annex is not None
    p = next(x for x in annex.parameters if x.parameter_name == "cot_theta_max")

    assert p.parameter_value is None
    assert p.validation_status is ValidationStatus.NOT_REPRESENTABLE
    assert p.en_recommended == 2.5          # what we did NOT store
    # La note pointe desormais la regle typee qui porte cette expression.
    assert "be.ec2.cot_theta_max" in (p.notes or "")


def test_unrepresentable_parameter_is_refused_even_outside_strict_mode() -> None:
    """Unlike an unverified value, no signature can unblock this one."""
    key = f"{EC2_11}:cot_theta_max"
    for strict in (False, True):
        ps = load_parameter_set("BE", strict=strict, as_of=AS_OF)
        with pytest.raises(UnrepresentableNationalParameter, match="pas de valeur"):
            ps.get(key)
        assert ps.preflight([key]).blocking[0].reason == "not_representable"


def test_unrepresentable_parameter_counts_as_unusable() -> None:
    ps = load_parameter_set("BE", strict=False, as_of=AS_OF)
    assert f"{EC2_11}:cot_theta_max" in ps.unverified_keys()


def test_a_value_may_not_go_missing_without_saying_why() -> None:
    """The absent value and the status that explains it are one invariant.

    A dropped key during an import would otherwise look exactly like a
    deliberate 'the annex gives a formula here'.
    """
    import dataclasses

    ps = load_parameter_set("BE", strict=False, as_of=AS_OF)
    annex = ps.registry.annexes[0]
    # Un parametre scalaire ordinaire, sans variantes.
    scalar = next(p for p in annex.parameters if p.parameter_name == "As_min_coeff")
    cot = next(p for p in annex.parameters if p.parameter_name == "cot_theta_max")

    with pytest.raises(ValueError, match="not_representable"):
        dataclasses.replace(scalar, parameter_value=None)     # value lost
    with pytest.raises(ValueError, match="not_representable"):
        dataclasses.replace(cot, parameter_value=2.5)         # value invented


# ---------------------------------------------------------------------------
# Parametres conditionnels — l'annexe donne plusieurs valeurs selon le cas
# ---------------------------------------------------------------------------
def test_belgian_alpha_cc_has_two_branches_and_no_default() -> None:
    """§3.1.6(1)P: 0,85 en flexion, 1,0 « pour les autres cas ».

    Aucune valeur unique n'est stockee. Un scalaire serait lu par tout module
    qui oublie de preciser sa verification — c'est exactement l'erreur que
    l'effort tranchant aurait commise en heritant du 0,85 de la flexion.
    """
    p = load_parameter_set("BE", strict=False, as_of=AS_OF).find(f"{EC2_11}:alpha_cc")
    assert p is not None
    assert p.is_conditional
    assert p.parameter_value is None
    assert set(p.conditions) == {"axial_and_bending", "other"}
    assert p.value_for("axial_and_bending") == 0.85
    assert p.value_for("other") == 1.0


def test_reading_a_conditional_parameter_without_a_case_is_refused() -> None:
    ps = load_parameter_set("BE", strict=False, as_of=AS_OF)
    with pytest.raises(ConditionalParameterNeedsContext, match="aucun cas"):
        ps.get(f"{EC2_11}:alpha_cc")


def test_an_unknown_case_is_refused_rather_than_approximated() -> None:
    ps = load_parameter_set("BE", strict=False, as_of=AS_OF)
    with pytest.raises(ConditionalParameterNeedsContext) as e:
        ps.get(f"{EC2_11}:alpha_cc", condition="fatigue")
    assert "n'est pas prevu" in str(e.value)
    assert e.value.conditions == ("axial_and_bending", "other")


def test_a_case_on_an_unconditional_parameter_is_accepted_and_noted() -> None:
    """Declarer son cas est toujours correct; brancher dessus regarde l'annexe.

    Cette regle etait d'abord posee a l'envers — un cas fourni la ou l'annexe
    n'en definit aucun etait refuse. Elle punissait l'appelant pour la forme de
    l'annexe: le module d'effort tranchant, correct en annonçant « other »,
    echouait sur la France dont alpha_cc est un simple scalaire. La valeur
    unique s'applique a tous les cas, et le journal dit que la distinction
    n'existe pas ici.
    """
    ps = load_parameter_set("FR", strict=False, as_of=AS_OF)
    j = Journal("test")
    assert ps.get(f"{EC2_11}:alpha_cc", j, condition="other").magnitude == 1.0
    detail = j.get(f"{EC2_11}:alpha_cc").provenance.detail
    assert "cas declare: other" in detail
    assert "ne distingue pas les cas" in detail


def test_a_conditional_parameter_may_not_also_carry_a_default() -> None:
    import dataclasses

    from eurostruct_engine.ndp.model import ParameterVariant

    ps = load_parameter_set("BE", strict=False, as_of=AS_OF)
    alpha = ps.find(f"{EC2_11}:alpha_cc")
    assert alpha is not None
    with pytest.raises(ValueError, match="valeur par defaut"):
        dataclasses.replace(alpha, parameter_value=0.85)
    with pytest.raises(ValueError, match="en double"):
        dataclasses.replace(
            alpha,
            variants=(*alpha.variants, ParameterVariant("other", 0.9, "doublon")),
        )


def test_flexure_declares_the_case_it_computes() -> None:
    """Le journal doit montrer QUELLE branche a servi, pas seulement sa valeur."""
    r = design_flexure(
        section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
        concrete=concrete("C30/37"), steel=reinforcement("B500B"),
        M_Ed=Q_(250, "kN*m"),
        params=load_parameter_set("BE", strict=False, as_of=AS_OF),
    )
    step = r.journal.get(f"{EC2_11}:alpha_cc")
    assert step.value.magnitude == 0.85
    assert "axial_and_bending" in step.provenance.detail


# ---------------------------------------------------------------------------
# Interdiction 4 — Spain is not a pure-Eurocode country
# ---------------------------------------------------------------------------
def test_spain_declares_its_binding_framework() -> None:
    reg = load_country_registry("ES")
    fw = reg.regulatory_framework
    assert "Codigo Estructural" in fw.binding_reference
    assert "CTE" in fw.binding_reference
    assert "NCSE-02" in fw.binding_reference
    assert "PAS" in fw.eurocode_status  # "n'est PAS un pays « Eurocode pur »"
    assert "visado colegial" in fw.verification_regime.lower()


def test_germany_declares_its_verification_regime() -> None:
    fw = load_country_registry("DE").regulatory_framework
    assert "MVV TB" in fw.binding_reference
    assert "Prufstatiker" in fw.verification_regime
    assert "Bauvorlageberechtigung" in fw.verification_regime


@pytest.mark.parametrize("country", ALL_COUNTRIES)
def test_regulatory_framework_reaches_the_note_de_calcul(country: str) -> None:
    """The note must state which framework the project was verified under."""
    summary = load_parameter_set(country, strict=False, as_of=AS_OF).summary()
    fw = summary["regulatory_framework"]
    assert fw["binding_reference"] and fw["eurocode_status"]
    assert fw["verification_regime"]


# ---------------------------------------------------------------------------
# Honesty of the shipped dataset
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("country", ALL_COUNTRIES)
def test_confirmed_values_carry_a_named_verifier(country: str) -> None:
    """Guards against a placeholder being flipped to 'confirmed' by accident."""
    reg = load_country_registry(country)
    for annex in reg.annexes:
        for p in annex.parameters:
            if p.validation_status is ValidationStatus.CONFIRMED:
                assert p.verified_by, (
                    f"{country}/{p.key} est 'confirmed' sans verified_by. "
                    "Renseigner qui a releve la valeur dans l'annexe publiee."
                )
                assert p.verified_at, f"{country}/{p.key}: verified_at manquant"
                assert p.source_type.value == "national_annex", (
                    f"{country}/{p.key}: une valeur confirmee doit venir de "
                    "l'Annexe Nationale, pas de la recommandation EN."
                )


@pytest.mark.parametrize("country", ALL_COUNTRIES)
def test_shipped_dataset_is_flagged_unverified(country: str) -> None:
    """No annex has been read yet, and the data says so."""
    ps = load_parameter_set(country, strict=False, as_of=AS_OF)
    assert set(ps.unverified_keys()) == set(ps.keys())


def test_calculation_freezes_the_parameter_set_it_used() -> None:
    r = design_flexure(
        section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
        concrete=concrete("C30/37"), steel=reinforcement("B500B"),
        M_Ed=Q_(250, "kN*m"),
        params=load_parameter_set("BE", strict=False, as_of=AS_OF),
    )
    ndp = r.ndp_summary
    assert ndp["country"] == "BE"
    assert ndp["as_of"] == "2026-07-26"
    assert ndp["annexes"][0]["reference"] == "NBN EN 1992-1-1 ANB"
    assert ndp["unverified"]              # honestly reported in the deliverable
    assert ndp["regulatory_framework"]["binding_reference"]


# ---------------------------------------------------------------------------
# value_provenance — d'ou vient le NOMBRE, pas de quel document
# ---------------------------------------------------------------------------
def test_a_eurocode_default_can_never_be_confirmed_as_national() -> None:
    """La contradiction que ce champ rend impossible a construire.

    Confirmer, c'est declarer « j'ai lu l'Annexe Nationale publiee et c'est
    bien cette valeur ». On ne peut pas le declarer d'un nombre dont la fiche
    elle-meme dit qu'il vient de la recommandation europeenne.

    Avant ce champ, rien de structurel ne l'empechait: il suffisait qu'un
    relecteur passe le statut a `confirmed` sur une fiche portant 0,6 semé
    depuis l'EN pour que le mode strict laisse passer une valeur europeenne
    presentee comme belge.
    """
    import datetime as _dt

    import pytest

    from eurostruct_engine.ndp import (
        NationalParameter,
        SourceType,
        ValidationStatus,
        ValueProvenance,
    )

    def build(prov):
        return NationalParameter(
            country_code="BE", standard_family="EN 1992", part="1-1",
            national_annex_reference="NBN EN 1992-1-1 ANB", edition="2010",
            effective_from=_dt.date(2010, 8, 1), effective_to=None,
            parameter_name="essai", parameter_value=0.6, unit="dimensionless",
            source_official="NBN", source_url_or_doc_id=None,
            source_doc_id="c" * 64, source_page=15,
            source_type=SourceType.NATIONAL_ANNEX,
            validation_status=ValidationStatus.CONFIRMED,
            verified_at="2026-08-15", verified_by="Relecteur Test",
            notes=None, clause="§6.2.2(6)", description="essai",
            value_provenance=prov,
        )

    for refuse in (
        ValueProvenance.EUROCODE_DEFAULT,
        ValueProvenance.NATIONAL_ANNEX_PENDING,
        ValueProvenance.INFERRED,
        ValueProvenance.USER_DEFINED,
    ):
        with pytest.raises(ValueError, match="confirmed"):
            build(refuse)

    # La seule combinaison admise, et elle est utilisable en mode strict.
    p = build(ValueProvenance.NATIONAL_ANNEX)
    assert p.usable_in_strict_mode


def test_provenance_is_derived_conservatively_when_absent() -> None:
    """Un enregistrement ecrit avant ce champ doit encore se charger.

    La derivation ne va que dans un sens sur: `en_recommended` devient
    EUROCODE_DEFAULT, ce qui BLOQUE. Une fiche qui est en realite une valeur
    d'attente doit le declarer elle-meme — aucune regle ne distingue une
    valeur d'attente d'une lecture, seul le lecteur le sait.
    """
    from eurostruct_engine.ndp import ValueProvenance, load_country_registry

    be = load_country_registry("BE")
    params = be.annexes[0].parameters
    by_name = {p.parameter_name: p for p in params}

    # Les six clauses jamais ouvertes portent la recommandation EN.
    assert by_name["nu1_coeff"].value_provenance is ValueProvenance.EUROCODE_DEFAULT
    assert not by_name["nu1_coeff"].value_provenance.is_national

    # w_max: etiquette national_annex, valeurs du tableau EN. C'est le cas qui
    # a motive le champ, et le seul ou provenance et source_type divergent.
    w = by_name["w_max"]
    assert w.source_type.value == "national_annex"
    assert w.value_provenance is ValueProvenance.NATIONAL_ANNEX_PENDING
    assert not w.value_provenance.is_national


# ---------------------------------------------------------------------------
# Le portillon du mode strict — mesure du 30/08/2026
# ---------------------------------------------------------------------------
def test_un_fichier_du_depot_ne_peut_pas_ouvrir_le_mode_strict(
    tmp_path, monkeypatch,
) -> None:
    """Ce que ce cas a trouve, et qui etait vrai avant lui.

    En basculant deux champs de ``be.json`` — ``validation_status`` a
    ``confirmed`` et ``value_provenance`` a ``national_annex`` — un calcul
    belge en mode **strict** aboutissait, et se declarait signable. Le
    verificateur etait la chaine de caracteres qu'on avait bien voulu ecrire.

    Le depot annoncait pourtant le contraire, en toutes lettres, dans
    ``confirmation.py``:

        « aucun fichier editable du depot ne peut rendre une regle REELLE
        strict-ready »

    Une garantie que rien n'exerce ne se distingue pas d'une garantie perdue:
    ``assert_provider_is_usable_in_production`` gardait un chemin que le calcul
    ne prend pas.

    LE CAS FAIT L'EDITION, il ne la simule pas. Verifier que la fonction de
    lecture refuse une chaine ne prouverait rien sur le chemin reel: c'est
    ``load_country_registry`` qui lit le fichier, et c'est lui qui doit
    refuser.
    """
    import json
    import shutil

    from eurostruct_engine.ndp import registry as _registry

    donnees = tmp_path / "data"
    shutil.copytree(_registry._DATA_DIR, donnees)

    be = donnees / "be.json"
    brut = json.loads(be.read_text(encoding="utf-8"))
    bascules = 0
    for annexe in brut["annexes"]:
        for item in annexe["parameters"].values():
            if item.get("validation_status") == "pending_verification":
                item["validation_status"] = "confirmed"
                item["value_provenance"] = "national_annex"
                item["source_type"] = "national_annex"
                item["verified_at"] = "2026-08-30"
                item["verified_by"] = "personne-qui-n-existe-pas"
                bascules += 1
    assert bascules > 0, "le jeu belge n'a plus de parametre a basculer"
    be.write_text(json.dumps(brut, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(_registry, "_DATA_DIR", donnees)
    _registry.load_country_registry.cache_clear()
    try:
        with pytest.raises(ValueError, match="ne peut pas porter le statut"):
            _registry.load_country_registry("BE")
    finally:
        # Le cache est global: le laisser charge depuis `tmp_path` ferait
        # dependre les cas suivants de l'ordre d'execution.
        _registry.load_country_registry.cache_clear()


def test_les_statuts_transcriptibles_excluent_confirmed() -> None:
    """La liste est la regle; ce cas empeche qu'on l'elargisse par megarde."""
    from eurostruct_engine.ndp.registry import STATUTS_TRANSCRIPTIBLES

    assert ValidationStatus.CONFIRMED.value not in STATUTS_TRANSCRIPTIBLES
    attendus = {"pending_verification", "deprecated", "not_representable"}
    assert set(STATUTS_TRANSCRIPTIBLES) == attendus


def test_un_statut_inconnu_dans_un_fichier_est_refuse_nommement() -> None:
    """Un statut inconnu ne doit pas se lire comme un statut permissif."""
    from eurostruct_engine.ndp.registry import _statut_transcrit

    with pytest.raises(ValueError, match="statut de validation inconnu"):
        _statut_transcrit("valide", "BE", "EN 1992-1-1:essai")
