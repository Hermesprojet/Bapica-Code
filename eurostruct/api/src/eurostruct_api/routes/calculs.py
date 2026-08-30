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
réponse porte ``signable: false`` et la mention **« PROJET — NON SIGNABLE »**.
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
    BeamSectionDrawingRequest,
    Ec2BeamFlexureRequest,
)
from eurostruct_engine.legal import Language, notice
from eurostruct_engine.service import render_beam_section, run_ec2_beam_flexure
from fastapi import APIRouter, Response

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
def flexion_poutre_ec2(requete: Ec2BeamFlexureRequest) -> dict[str, Any]:
    """Vérification ELU en flexion simple, section rectangulaire.

    Rend la réponse du contrat, augmentée des seuls champs que la couche HTTP a
    le droit d'ajouter : le caractère signable — conséquence directe de
    ``strict_ndp``, pas une donnée d'ingénierie — et la mention obligatoire.

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
    reponse = run_ec2_beam_flexure(requete)
    corps = reponse.model_dump(mode="json")
    corps["signable"] = bool(requete.strict_ndp)
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
def section_poutre_dxf(requete: BeamSectionDrawingRequest) -> Response:
    """Rend le DXF de la section, et le tableau d'armatures dans l'en-tête.

    LE DXF EST LE CORPS, PAS UN CHAMP D'UN JSON. Un fichier de dessin encodé
    en base64 dans une enveloppe oblige chaque client à le décoder avant de
    l'ouvrir ; servi tel quel, il se télécharge et s'ouvre.
    """
    document, tableau = render_beam_section(requete)
    tampon = io.StringIO()
    document.write(tampon)
    contenu = tampon.getvalue().encode("utf-8")

    nom = f"{requete.element or 'section'}.dxf".replace(" ", "_")
    return Response(
        content=contenu,
        media_type="image/vnd.dxf",
        headers={
            "Content-Disposition": f'attachment; filename="{nom}"',
            # Le tableau d'armatures voyage en en-tete pour rester lisible
            # sans ouvrir le DXF. Il ne contient que des entiers et des
            # reperes: aucune donnee personnelle, aucun secret.
            "X-Eurostruct-Rebar-Rows": str(len(tableau)),
        },
    )
