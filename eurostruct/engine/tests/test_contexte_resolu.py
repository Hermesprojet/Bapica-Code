"""Un seul jeu de paramètres, une seule identité, quatre empreintes nommées.

CE QUE CE FICHIER EXISTE POUR ATTRAPER
---------------------------------------
Trois incohérences introduites par la tranche HTTP précédente, et chacune est
silencieuse : le produit rend un 201, la ligne s'écrit, et pourtant quelque
chose ne tient pas.

1. **LE JEU RÉSOLU ÉTAIT PERDU.** La route appelait `preflight_beam(provider=)`
   — qui applique les confirmations et rend un jeu où seuls les paramètres
   confirmés sont utilisables — puis rechargeait le référentiel BRUT par
   `load_parameter_set`. Le travail du provider était jeté entre le préflight
   et le moteur. Conséquence : un préflight strict « prêt » suivi d'un calcul
   strict qui refuse, sur le même dossier, à la même seconde.

2. **DEUX IDENTITÉS D'EXÉCUTION.** Elle était calculée une fois avec
   `ndp=None` et passée au moteur, puis RECALCULÉE avec l'instantané normatif
   pour la persistance. L'étude portait donc une identité, la base une autre.
   Une note qui cite la première ne se rattache à aucune ligne.

3. **UNE EMPREINTE PARTIELLE SOUS UN NOM QUI PROMET LA TOTALITÉ.**
   `calculations.inputs_hash` est documentée comme l'empreinte de toutes les
   entrées ; on y écrivait l'empreinte des seules données techniques. Deux
   études identiques sous des référentiels différents la partageaient.

LES QUATRE EMPREINTES, ET CE QUE CHACUNE COUVRE
-------------------------------------------------
    engineering_inputs_hash   géométrie, sollicitations, ferraillage
    ndp_snapshot_id           le référentiel exact, résolu
    calculation_fingerprint   l'étude complète: technique + contexte normatif
    execution_identity        l'étude complète + moteur et build

Aucune ne se substitue à une autre, et c'est le sujet : celle qui promet la
totalité doit la couvrir.
"""

from __future__ import annotations

from datetime import date

import pytest

from eurostruct_engine.ec2 import ExposureClass, StructuralSystem
from eurostruct_engine.ec2.anchorage import BondCondition
from eurostruct_engine.ec2.beam_verification import (
    BeamGeometry,
    BeamVerificationInput,
    LongitudinalBars,
    TransverseLinks,
    resolve_beam_context,
    verify_beam,
)
from eurostruct_engine.units import Q_

AS_OF = date(2026, 1, 1)


def _entree(**remplace):
    base = dict(
        element="P1",
        geometry=BeamGeometry(b=Q_(300, "mm"), h=Q_(600, "mm"),
                              d=Q_(550, "mm"), l_eff=Q_(6000, "mm")),
        concrete_grade="C30/37", steel_grade="B500B",
        M_Ed=Q_(250, "kN*m"), V_Ed=Q_(300, "kN"),
        M_char=Q_(180, "kN*m"), M_qp=Q_(120, "kN*m"),
        phi_creep=2.0,
        exposure_class=ExposureClass.XC3,
        system=StructuralSystem.SIMPLY_SUPPORTED,
        bars=LongitudinalBars(count=4, diameter=Q_(20, "mm")),
        links=TransverseLinks(legs=2, diameter=Q_(10, "mm"),
                              spacing=Q_(150, "mm")),
        cot_theta=1.5, cover=Q_(40, "mm"),
        bond_condition=BondCondition.GOOD,
        anchorage_available=Q_(800, "mm"),
    )
    base.update(remplace)
    return BeamVerificationInput(**base)


# ---------------------------------------------------------------------------
# 1. UN SEUL JEU DE PARAMÈTRES, RÉSOLU UNE FOIS
# ---------------------------------------------------------------------------
def test_le_contexte_rend_le_jeu_qui_a_servi_au_preflight() -> None:
    """LE MÊME OBJET, PAS UN JEU ÉQUIVALENT.

    Rendre un jeu « rechargé avec les mêmes arguments » laisserait revenir le
    défaut au premier provider qui change quelque chose : deux lectures du même
    référentiel ne sont égales que tant que rien ne les distingue.
    """
    ctx = resolve_beam_context(country="BE", as_of=AS_OF, strict=False)
    assert ctx.parameters is ctx.preflight_parameters, (
        "le jeu du préflight et celui du calcul doivent être le MÊME objet")


def test_le_contexte_porte_preflight_instantane_et_empreinte() -> None:
    ctx = resolve_beam_context(country="BE", as_of=AS_OF, strict=False)
    assert ctx.preflight.ready
    assert ctx.ndp_snapshot["country"] == "BE"
    assert len(ctx.ndp_snapshot_id) == 64
    assert ctx.parameters.strict is False


def test_le_contexte_strict_sans_provider_n_est_pas_pret() -> None:
    ctx = resolve_beam_context(country="BE", as_of=AS_OF, strict=True)
    assert not ctx.preflight.ready
    assert any(b.reason == "pending_verification"
               for b in ctx.preflight.blocking)


def test_l_etude_tourne_sur_le_jeu_resolu_du_contexte() -> None:
    """LA PREUVE QUE RIEN N'EST RECHARGÉ ENTRE LES DEUX."""
    ctx = resolve_beam_context(country="BE", as_of=AS_OF, strict=False)
    etude = verify_beam(_entree(), params=ctx.parameters)
    assert etude.ndp_snapshot_id == ctx.ndp_snapshot_id, (
        "l'instantané de l'étude diffère de celui du contexte: un jeu a été "
        "rechargé entre le préflight et le moteur")


def test_un_provider_qui_confirme_change_le_jeu_resolu() -> None:
    """CE QUE LE PROVIDER FAIT DOIT SURVIVRE JUSQU'AU MOTEUR.

    On ne vérifie pas ici qu'un provider FICTIF débloque le calcul — il ne le
    doit pas, et `test_verification_poutre` le dit. On vérifie que le contexte
    INTERROGE le provider et porte sa trace: un contexte qui l'ignorerait
    rendrait exactement le même objet, et rien ne le distinguerait.
    """
    from eurostruct_engine.ndp.confirmation import InMemoryConfirmationProvider

    provider = InMemoryConfirmationProvider(confirmations=(), revocations=())
    ctx = resolve_beam_context(country="BE", as_of=AS_OF, strict=True,
                               provider=provider)
    assert ctx.preflight.provider_identity is not None
    assert ctx.preflight.provider_is_fictional is True


# ---------------------------------------------------------------------------
# 2. UNE SEULE IDENTITÉ D'EXÉCUTION
# ---------------------------------------------------------------------------
def test_l_identite_se_calcule_une_fois_et_porte_l_instantane() -> None:
    """ELLE EST CALCULÉE APRÈS LA RÉSOLUTION, JAMAIS AVANT.

    Une identité calculée avec `ndp=None` puis recalculée avec l'instantané
    donne DEUX valeurs pour une même exécution. L'étude en porte une, la base
    l'autre, et une note qui cite la première ne se rattache à aucune ligne.
    """
    ctx = resolve_beam_context(country="BE", as_of=AS_OF, strict=False)
    charge = {"element": "P1", "country": "BE"}
    a = ctx.execution_identity(charge, engine_build="FICTIF-build")
    b = ctx.execution_identity(charge, engine_build="FICTIF-build")
    assert a == b, "l'identité doit être déterministe"
    assert len(a) == 64


def test_l_identite_change_avec_le_referentiel_resolu() -> None:
    """Deux référentiels, deux identités — même requête, même build."""
    charge = {"element": "P1"}
    be = resolve_beam_context(country="BE", as_of=AS_OF, strict=False)
    fr = resolve_beam_context(country="FR", as_of=AS_OF, strict=False)
    assert (be.execution_identity(charge, engine_build="X")
            != fr.execution_identity(charge, engine_build="X"))


def test_l_identite_change_avec_le_build() -> None:
    ctx = resolve_beam_context(country="BE", as_of=AS_OF, strict=False)
    charge = {"element": "P1"}
    assert (ctx.execution_identity(charge, engine_build="A")
            != ctx.execution_identity(charge, engine_build="B"))


# ---------------------------------------------------------------------------
# 3. QUATRE EMPREINTES NOMMÉES, ET CELLE QUI PROMET LA TOTALITÉ LA COUVRE
# ---------------------------------------------------------------------------
def test_les_quatre_empreintes_portent_des_noms_exacts() -> None:
    ctx = resolve_beam_context(country="BE", as_of=AS_OF, strict=False)
    etude = verify_beam(_entree(), params=ctx.parameters)

    assert len(etude.engineering_inputs_hash) == 64
    assert len(etude.ndp_snapshot_id) == 64
    assert len(etude.calculation_fingerprint) == 64

    d = etude.to_dict()
    for cle in ("engineering_inputs_hash", "ndp_snapshot_id",
                "calculation_fingerprint"):
        assert cle in d, f"« {cle} » manque au dictionnaire de l'étude"

    #: `inputs_hash` NE DOIT PLUS EXISTER SOUS CE NOM DANS LE MOTEUR: il
    #: promettait la totalité et ne portait que la technique.
    assert "inputs_hash" not in d


def test_deux_referentiels_partagent_la_technique_pas_l_etude() -> None:
    """LE CŒUR DE LA TROISIÈME INCOHÉRENCE.

    Les mêmes nombres sous deux annexes ne sont pas la même étude. Ils
    partagent l'empreinte TECHNIQUE — c'est exact et utile — et ne doivent
    surtout pas partager l'empreinte COMPLÈTE.
    """
    be = resolve_beam_context(country="BE", as_of=AS_OF, strict=False)
    fr = resolve_beam_context(country="FR", as_of=AS_OF, strict=False)
    a = verify_beam(_entree(), params=be.parameters)
    b = verify_beam(_entree(), params=fr.parameters)

    assert a.engineering_inputs_hash == b.engineering_inputs_hash
    assert a.ndp_snapshot_id != b.ndp_snapshot_id
    assert a.calculation_fingerprint != b.calculation_fingerprint


@pytest.mark.parametrize("libelle,remplace", [
    ("le moment", {"M_Ed": Q_(260, "kN*m")}),
    ("les barres", {"bars": LongitudinalBars(count=5,
                                             diameter=Q_(20, "mm"))}),
    ("les cadres", {"links": TransverseLinks(legs=2, diameter=Q_(8, "mm"),
                                             spacing=Q_(200, "mm"))}),
])
def test_changer_une_donnee_technique_change_les_deux_empreintes(
        libelle, remplace) -> None:
    ctx = resolve_beam_context(country="BE", as_of=AS_OF, strict=False)
    a = verify_beam(_entree(), params=ctx.parameters)
    b = verify_beam(_entree(**remplace), params=ctx.parameters)
    assert a.engineering_inputs_hash != b.engineering_inputs_hash, libelle
    assert a.calculation_fingerprint != b.calculation_fingerprint, libelle
