"use client";

/**
 * La synthèse d'une étude : cinq chapitres, un verdict, et ce qu'on peut en
 * faire.
 *
 * QUATRE ÉTATS, QUATRE COULEURS, AUCUNE FUSION
 * ---------------------------------------------
 * `passed`, `failed`, `additional_analysis_required`, `not_evaluated`. Les
 * deux derniers sont ceux qu'on est tenté de ranger avec les deux premiers, et
 * c'est exactement ce qu'il ne faut pas faire :
 *
 *   — une **analyse complémentaire due** n'est pas un échec. Le moteur n'a pas
 *     trouvé la section fautive ; il a trouvé que la question sort de son
 *     domaine. La peindre en rouge ferait corriger une poutre qui va bien.
 *
 *   — une section **non évaluée** n'est pas une réussite. C'est le cas
 *     français : son Annexe Nationale rend k₃ fonction de l'enrobage, une
 *     FORMULE que le modèle scalaire ne sait pas porter. La peindre en vert
 *     ferait signer une étude dont un chapitre n'a jamais tourné.
 *
 * L'ÉCRAN NE DÉCIDE D'AUCUN VERDICT. Il affiche `status`, `utilisation` et
 * `remedy` tels que le serveur les rend. Il ne recompose pas le statut global
 * à partir des cinq — le serveur le rend aussi — et il ne recalcule aucun taux.
 */
import {
  ETAT_CLASSE, ETAT_LISIBLE, raisonDeNonFinalisation,
  type Ec2BeamVerificationResponse, type SectionOutcomeDTO,
} from "@/lib/verification";

/** Les trois statuts d'ensemble du contrat, en clair. */
const VERDICT: Record<string, string> = {
  passed: "Les cinq chapitres sont vérifiés",
  failed: "Au moins un chapitre n'est pas vérifié",
  incomplete: "L'étude ne conclut pas",
};

export function SyntheseEtude({ etude, actions }: {
  etude: Ec2BeamVerificationResponse;
  //: Les actions sont fournies par le parent — il détient la session et les
  //: droits. Ce composant ne sait ni télécharger ni écrire.
  actions?: React.ReactNode;
}) {
  const raison = raisonDeNonFinalisation(etude);
  const classe = etude.status === "passed" ? "ok"
    : etude.status === "failed" ? "refus" : "alerte";

  return (
    <section aria-labelledby="titre-synthese" id="synthese-etude"
             data-calcul={etude.calculation_id} data-statut={etude.status}>
      <h2 id="titre-synthese">Étude {etude.element}</h2>

      <div className={`bandeau ${classe}`} id="verdict-etude" role="status">
        <strong>{VERDICT[etude.status] ?? etude.status}</strong>
        {etude.notice}
      </div>

      {/* LA MENTION EST DANS LA RÉPONSE, et l'écran la rend telle quelle. La
          recomposer ici donnerait une seconde formulation de la même
          obligation — et un jour, une seule des deux serait corrigée. */}
      {etude.mention && (
        <p className="mention-non-signable">{etude.mention}</p>
      )}

      <table>
        <caption className="aide">
          Les cinq chapitres, dans l&apos;ordre où le moteur les enchaîne.
        </caption>
        <thead>
          <tr>
            <th scope="col">Chapitre</th>
            <th scope="col">Base</th>
            <th scope="col">État</th>
            <th scope="col">Taux</th>
          </tr>
        </thead>
        <tbody>
          {(etude.sections ?? []).map((s) => (
            <LigneChapitre key={s.key} section={s} />
          ))}
        </tbody>
      </table>

      {/* CE QUI EMPÊCHE DE FINALISER EST ÉCRIT, PAS DEVINÉ. Un bouton grisé
          sans motif oblige l'ingénieur à chercher — et la cause la plus
          fréquente, l'étude exploratoire, ne se corrige pas en modifiant la
          section. */}
      {raison ? (
        <p className="bandeau alerte" id="pourquoi-non-finalisable"
           role="status">
          <strong>Cette étude ne peut pas être finalisée</strong>
          {raison}
        </p>
      ) : (
        <p className="bandeau ok" id="etude-finalisable" role="status">
          <strong>Étude finalisable</strong>
          Les cinq chapitres sont vérifiés sous des paramètres nationaux
          confirmés. La signature reste un acte humain, qu&apos;aucun calcul ne
          remplace.
        </p>
      )}

      {actions}

      <Tracabilite etude={etude} />
    </section>
  );
}

function LigneChapitre({ section }: { section: SectionOutcomeDTO }) {
  const etat = ETAT_LISIBLE[section.status] ?? section.status;
  return (
    <>
      <tr id={`chapitre-${section.key}`} data-etat={section.status}>
        <th scope="row">{section.title}</th>
        <td className="clause">{section.basis}</td>
        <td>
          <span className={`etat ${ETAT_CLASSE[section.status] ?? "silence"}`}>
            {etat}
          </span>
        </td>
        <td className="nombre">
          {/* PAS DE « 0 % » QUAND LA SECTION N'A PAS TOURNÉ. Un taux suppose un
              calcul; en afficher un pour une section non évaluée serait
              inventer un résultat. */}
          {typeof section.utilisation === "number"
            ? `${(section.utilisation * 100).toFixed(1)} %`
            : "—"}
        </td>
      </tr>
      {(section.remedy || section.reason) && (
        <tr>
          <td colSpan={4} className="clause">
            {section.remedy}
            {section.reason && (
              <> <code>{section.reason}</code></>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

/**
 * Les empreintes, et ce que chacune promet.
 *
 * ELLES NE SE SUBSTITUENT PAS L'UNE À L'AUTRE, et les afficher ensemble est le
 * seul moyen de le rendre visible : deux études identiques sous des annexes
 * différentes partagent `engineering_inputs_hash` et rien d'autre.
 */
function Tracabilite({ etude }: { etude: Ec2BeamVerificationResponse }) {
  const lignes: ReadonlyArray<readonly [string, string, string]> = [
    ["Entrées d'ingénierie", etude.engineering_inputs_hash,
     "Géométrie, sollicitations, ferraillage. Elle ne dit rien du référentiel."],
    ["Instantané normatif", etude.ndp_snapshot_id,
     "L'édition exacte des paramètres nationaux résolus pour cette étude."],
    ["Empreinte du calcul", etude.calculation_fingerprint,
     "L'étude complète : entrées ET référentiel."],
    ["Identité d'exécution", etude.execution_identity,
     `L'étude complète, plus le moteur ${etude.engine_version} `
     + `et le build ${etude.engine_build_sha}.`],
  ];
  return (
    <details>
      <summary>Traçabilité</summary>
      <table>
        <tbody>
          {lignes.map(([nom, valeur, sens]) => (
            <tr key={nom}>
              <th scope="row">{nom}</th>
              <td>
                <code>{valeur}</code>
                <span className="aide">{sens}</span>
              </td>
            </tr>
          ))}
          <tr>
            <th scope="row">Référentiel</th>
            <td>
              {etude.country}
              {etude.region ? ` — ${etude.region}` : ""}
              {` — ${etude.ndp_as_of}`}
              <span className="aide">
                Figé sur le projet, jamais nommé par la requête.
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </details>
  );
}
