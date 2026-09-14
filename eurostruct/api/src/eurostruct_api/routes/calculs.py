"""Les calculs. Le moteur décide, la couche HTTP transporte.

CE QUE CES ROUTES NE FONT PAS
------------------------------
Elles ne calculent rien. Aucune formule, aucun coefficient, aucun arrondi
n'apparaît ici : tout passe par ``eurostruct_engine.service``, qui est le seul
adaptateur entre le contrat de fil et le domaine. Une valeur recalculée dans
la couche HTTP serait une seconde vérité, non éprouvée.

``strict_ndp`` N'EST PAS TOUCHÉ
--------------------------------
Il vaut ``true`` par défaut dans le contrat, et cette couche ne le renverse
jamais. Quand l'appelant demande explicitement ``strict_ndp=false``, la
réponse porte ``exploratory: true`` et la mention **« PROJET — NON SIGNABLE »**.
Un calcul exploratoire est une aide au dimensionnement ; ce n'est pas une note
qu'un ingénieur peut signer.

LES REFUS
----------
``run_ec2_beam_flexure`` lève ; le gestionnaire global rend le
``EngineErrorDTO`` en **422**. Aucune route n'attrape le refus pour en faire
un corps de succès avec un champ ``ok: false``.
"""
from __future__ import annotations

import io
from typing import Any

from eurostruct_engine.schemas.ec2_beam import (
    Ec2BeamFlexureRequest,
    Ec2BeamSectionRequest,
)
from eurostruct_engine.legal import Language, notice
from eurostruct_engine.service import (
    run_ec2_beam_flexure,
    verify_and_render_beam_section,
)
from fastapi import APIRouter, Depends, Response

from ..dependances import provider_de_lecture

routeur = APIRouter(prefix="/v1/calculations", tags=["calculs"])

#: Ce que porte une réponse dont les NDP ne sont pas confirmés. La mention est
#: dans la réponse, pas seulement dans l'interface: une note produite par un
#: autre client doit la porter aussi.
MENTION_NON_SIGNABLE = "PROJET — NON SIGNABLE"

#: La mention obligatoire du cahier des charges §9, **sur toute réponse**.
#:
#: POURQUOI ELLE N'ÉTAIT PAS LÀ, ET POURQUOI C'EST UN DÉFAUT. Le DXF la porte
#: — `legal.py` l'y inscrit, et `test_dxf.py` le vérifie. La réponse JSON, non.
#: Or c'est elle qu'un client transforme en note de calcul : le jour où des
#: paramètres nationaux seront confirmés, un calcul strict rendrait un résultat
#: sans mention, et chaque client devrait penser à l'ajouter.
#:
#: L'interdiction n° 8 ne dit pas « sur les dessins » : elle dit « ne jamais
#: livrer un document sans la mention de validation par un ingénieur ».
MENTION_OBLIGATOIRE = notice(Language.FR)


@routeur.post("/ec2/beam-flexure")
def flexion_poutre_ec2(
    requete: Ec2BeamFlexureRequest,
    lecture: Any = Depends(provider_de_lecture),
) -> dict[str, Any]:
    """Vérification ELU en flexion simple, section rectangulaire.

    QUATRE CHAMPS AJOUTÉS, ET AUCUN NE DIT « SIGNABLE »
    ----------------------------------------------------
    Une rédaction antérieure rendait ``signable = bool(strict_ndp)``. C'était
    une promesse que rien ici ne tient : signer une note exige une validation
    humaine, un circuit documentaire et des garanties de commercialisation.
    Aucun de ces trois éléments n'existe dans cette réponse. Le mode strict dit
    seulement d'où viennent les nombres.

    ``strict_ndp_satisfied``
        Le calcul a tourné en mode strict et a abouti : tous les paramètres
        nationaux qu'il demande étaient confirmés et utilisables. C'est un
        fait sur les **valeurs**, et rien d'autre.

    ``eligible_for_engineering_review``
        Le plus qu'on puisse dire : ce résultat peut être **soumis** à un
        ingénieur. Pas qu'il est signé, ni signable.

    ``exploratory``
        ``strict_ndp=false`` : des valeurs non confirmées ont pu servir.

    ``notice`` ET ``mention`` NE DISENT PAS LA MÊME CHOSE, et les confondre
    serait une régression :

    ``notice``
        « ce document doit être vérifié et signé par un ingénieur habilité ».
        Vraie de **toute** réponse, y compris d'un calcul parfaitement strict :
        aucun logiciel ne signe une note.

    ``mention``
        « PROJET — NON SIGNABLE ». Bien plus forte, et **conditionnelle** : le
        calcul a utilisé des paramètres nationaux non confirmés, donc il ne
        peut pas être signé du tout, quel que soit l'ingénieur.

    La première dit « pas encore signé » ; la seconde « pas signable ».
    """
    # LE PROVIDER EST LA SOURCE DES CONFIRMATIONS, et c'est par lui que le
    # mode strict s'ouvre — jamais par un fichier du depot. `None` signifie
    # « aucune source connue »: le moteur refuse alors en strict, ce qui est
    # l'etat reel du referentiel aujourd'hui.
    try:
        reponse = run_ec2_beam_flexure(
            requete, provider=lecture.provider if lecture else None)
    finally:
        if lecture is not None:
            lecture.fermer()
    corps = reponse.model_dump(mode="json")
    strict = bool(requete.strict_ndp)
    # Aboutir en mode strict VEUT DIRE que le portillon a laissé passer: un
    # paramètre non confirmé aurait levé avant d'arriver ici.
    corps["strict_ndp_satisfied"] = strict
    corps["eligible_for_engineering_review"] = strict
    corps["exploratory"] = not strict
    corps["notice"] = MENTION_OBLIGATOIRE
    if not requete.strict_ndp:
        corps["mention"] = MENTION_NON_SIGNABLE
        corps["avertissement"] = (
            "strict_ndp=false: des parametres nationaux non confirmes ont pu "
            "etre utilises. Ce resultat est exploratoire et ne peut pas etre "
            "signe."
        )
    return corps


@routeur.post("/ec2/beam-section.dxf")
def section_poutre_dxf(requete: Ec2BeamSectionRequest) -> Response:
    """Vérifie le ferraillage choisi, **puis** rend le DXF.

    LA REQUÊTE PORTE LE CALCUL, PAS UNE GÉOMÉTRIE LIBRE
    ----------------------------------------------------
    Mesuré le 30/08 : l'interface envoyait ici une section codée en dur, et
    l'endpoint la dessinait — correctement, puisqu'il n'avait aucun moyen de
    savoir ce qui avait été calculé. L'ingénieur recevait le plan d'une poutre
    jamais vérifiée, à son propre repère.

    En recevant la **requête de calcul elle-même**, l'écart devient
    inconstructible : la section dessinée et la section vérifiée sont le même
    objet. `A_s_provided` n'est pas reçu — le moteur le dérive des barres, si
    bien qu'aucun appelant ne peut annoncer une aire que son ferraillage n'a
    pas.

    UN REFUS NE PRODUIT AUCUN FICHIER. Si la section ainsi ferraillée ne
    vérifie pas, la réponse est un 422 qui nomme le contrôle en défaut, et rien
    n'est téléchargé : un dessin qui échoue à sa propre vérification a l'air
    d'un dessin valide entre les mains de celui qui l'ouvre.

    LE DXF EST LE CORPS, PAS UN CHAMP D'UN JSON. Servi tel quel, il se
    télécharge et s'ouvre sans décodage.
    """
    document, tableau, reponse = verify_and_render_beam_section(requete)
    tampon = io.StringIO()
    document.write(tampon)
    contenu = tampon.getvalue().encode("utf-8")

    nom = f"{requete.calculation.element or 'section'}.dxf".replace(" ", "_")
    return Response(
        content=contenu,
        media_type="image/vnd.dxf",
        headers={
            "Content-Disposition": f'attachment; filename="{nom}"',
            # Le tableau d'armatures et l'utilisation voyagent en en-tete pour
            # rester lisibles sans ouvrir le DXF. Rien que des nombres et des
            # reperes: aucune donnee personnelle, aucun secret.
            "X-Eurostruct-Rebar-Rows": str(len(tableau)),
            "X-Eurostruct-Utilisation": f"{reponse.verification.max_utilisation:.3f}",
        },
    )
