/**
 * GENERATED FILE — DO NOT EDIT.
 *
 * Produced by engine/scripts/export_contracts.py from the Pydantic models in
 * engine/src/eurostruct_engine/schemas/. Edit those, then re-run:
 *
 *     cd engine && python scripts/export_contracts.py
 *
 * CI fails if this file is out of date with the models.
 *
 * Every physical value crosses the wire as a QuantityDTO carrying its unit.
 * There are no bare numbers for dimensional quantities, by design.
 */

/* eslint-disable */

/** La confirmation d'une modification, relue depuis la base. */
export interface AdhesionModifiee {
  is_active: boolean;
  role: string;
  user_id: string;
}

/** Ce que le validateur écrit, et **rien d'autre**. NI NOM, NI RÔLE, NI NUMÉRO D'INSCRIPTION. Les trois sortent de ``organization_members`` sous l'identité du jeton. Les accepter ici donnerait l'illusion qu'ils comptent, alors que PostgreSQL les écrase de toute façon — et l'illusion est pire que l'absence, parce qu'un écran finirait par les afficher. NI IDENTIFIANT DE CALCUL, NI EMPREINTE. L'attestation porte sur le calcul du livrable et sur les octets réellement enregistrés ; les faire venir du corps laisserait attester un calcul et en signer un autre. */
export interface AttestationDemande {
  /** Réserves émises par le validateur. Elles font partie de l'attestation et sont conservées avec elle. */
  reservations?: string | null;
  /** Ce que le validateur atteste, dans ses termes. Repris tel quel dans la ligne de validation, horodaté et figé. */
  statement: string;
}

/** The decision was spent. Exactly once: a replay is refused. */
export interface AuthorityDecisionConsumed {
  consumed: boolean;
  decision_id: string;
}

/** A decision now exists, and it is PENDING. Nothing is confirmed yet. */
export interface AuthorityDecisionCreated {
  decision_id: string;
}

/** What the decision is about. Never who proposes it. */
export interface AuthorityDecisionRequest {
  /** ISO 3166-1 alpha-2 code of the national annex concerned. */
  country_code: string;
  /** Edition of the standard the decision is scoped to. */
  edition: string;
  /** Tenant scope, or null for a referential-wide decision. */
  org_id?: string | null;
  part: string;
  permission: string;
  /** Human-readable motive. A datum, never a proof. */
  reason: string;
  /** The dossier presented to both engineers. Required when subject_kind is 'ndp_parameter': without it the decision could be approved and consumed without producing any normative effect. */
  review_package?: AuthorityReviewPackage | null;
  standard_family: string;
  /** Identifier of the subject the decision bears on. */
  subject_id: string;
  /** Nature of the subject, e.g. 'ndp_parameter'. */
  subject_kind: string;
}

/** A frozen decision, read back so the SECOND engineer can judge it. NO ACTOR IS RETURNED. B does not need to know who proposed in order to judge what was proposed, and PostgreSQL refuses a self-approval by table constraint rather than by the caller's prudence. Returning proposer and approver would turn a dossier read into a directory of licensed engineers. */
export interface AuthorityDecisionReview {
  country_code: string;
  decision_id: string;
  /** Recomputed by the server from the frozen payloads. */
  digests?: Record<string, string>;
  edition: string;
  org_id: string | null;
  /** The frozen dossier. Null only for a non-NDP subject. */
  package?: AuthorityReviewPackage | null;
  part: string;
  permission: string;
  proposed_at: string;
  reason: string;
  standard_family: string;
  state: string;
  subject_id: string;
  subject_kind: string;
}

/** What a named engineer transcribed from the published document. THE SERVER CANNOT PRODUCE THIS. Everything else in a dossier is derived from the registry — value, unit, provenance, annex reference, edition, clause, document digest. The quote is the one thing that only exists because somebody opened the annex at that page and read it. Inventing it would empty the four-eyes rule of its object. */
export interface AuthorityReviewCitation {
  /** Which required document this quote covers. */
  document_digest: string;
  /** PDF page number, when it differs. */
  page_pdf?: number | null;
  /** Printed folio, as it appears on the page itself. */
  page_printed: number;
  quote: string;
}

/** The composed dossier: what to propose, what to show, nothing invented. ``package`` is what goes back on the wire at proposal time. ``digests`` and ``summary`` are for the screen — the browser displays them, it does not compute them and has no way to. */
export interface AuthorityReviewDossier {
  digests: Record<string, string>;
  package: AuthorityReviewPackage;
  summary: Record<string, unknown>;
}

/** Ask the server to compose the dossier of one registry parameter. THE CLIENT SUPPLIES PROOF, NEVER SPECIFICATION. It names the parameter and hands over the human material — what a person read, where, and what they certify. Everything normative is derived server-side: * the value, unit, provenance, annex, edition, clause and document digest come from the registry; * what the clause *does* is a function of those registry fields; * the implementation fingerprint is a function of the declared code path that reads and applies the rule, plus the engine version. ``implementation_note`` AND ``effect`` USED TO BE FIELDS HERE, and both fed a canonical payload. Two people describing the same clause differently therefore signed two different subjects, and the code could change under a confirmation without invalidating it. ``Strict`` forbids extra fields, so a client still sending them now gets a 422 rather than a silent effect. */
export interface AuthorityReviewDraftRequest {
  /** One per document the specification declares. */
  citations: AuthorityReviewCitation[];
  country_code: string;
  rule_id: string;
  /** What the two reviewers declare they read and checked. */
  statement: string;
}

/** The dossier the two engineers are shown, frozen at proposal time. WHY IT TRAVELS WITH THE PROPOSAL AND NOT WITH THE APPROVAL. "B approved" means nothing unless the record says *what* B approved. The dossier is written once, at proposal, and PostgreSQL freezes it: A and B therefore approve byte-identical content, and the effect produced at consumption is that content and no other. NO DIGEST IS CARRIED HERE. The server recomputes every one of them from the payloads below. Accepting a digest would let a caller announce a fingerprint that does not summarise what is stored. */
export interface AuthorityReviewPackage {
  canonicalization_version: string;
  digest_algorithm: string;
  evidence_payload: string;
  implementation_payload: string;
  normative_spec_payload: string;
  /** Exact parameter identifier, e.g. 'EN 1992-1-1:alpha_cc'. */
  rule_id: string;
  stack_payload: string;
  /** What the reviewers declare they read and checked. */
  statement: string;
}

export interface BarRowDTO {
  count: number;
  /** Nominal bar diameter, mm */
  diameter: number;
  /** Developed length, mm */
  length?: number | null;
  mark: string;
}

/** La section et la portée, une seule fois pour les cinq modules. */
export interface BeamGeometryDTO {
  b: QuantityDTO;
  d: QuantityDTO;
  h: QuantityDTO;
  /** Portée utile, §5.3.2.2. Elle sert à la dispense du calcul de flèche. */
  l_eff: QuantityDTO;
}

/** Input of the DXF cross-section generator. Kept as the **drawing** contract: it knows a geometry and bars, and nothing about whether they were verified. :class:`Ec2BeamSectionRequest` is what a client should send; this one is what the renderer consumes once the check has passed. */
export interface BeamSectionDrawingRequest {
  /** Width, mm */
  b: number;
  bottom?: BarRowDTO[];
  concrete_grade?: string;
  /** Nominal cover c_nom, mm */
  cover: number;
  date?: string;
  element?: string;
  exposure_class?: string;
  /** Overall depth, mm */
  h: number;
  index?: string;
  /** Link diameter, mm */
  link_diameter: number;
  link_mark?: string;
  link_spacing?: number | null;
  /** Mention supplementaire portee au cartouche, par exemple « PROJET — NON SIGNABLE » quand des parametres nationaux non confirmes ont pu servir. Distincte du filigrane « NON VALIDE », qui parle de la validation par un ingenieur et non du referentiel employe. */
  mention?: string;
  plot_scale?: number;
  project?: string;
  steel_grade?: string;
  top?: BarRowDTO[];
}

/** One reason a calculation cannot proceed — TICKET 1.3. */
export interface BlockingParameterDTO {
  clause?: string | null;
  detail: string;
  key: string;
  national_annex_reference?: string | null;
  parameter_name: string;
  /** Machine-readable cause, for CI. */
  reason: "annex_missing" | "missing" | "pending_verification" | "deprecated";
  standard: string;
}

/** One traceable line of the calculation — see section 8.1. */
export interface CalcStepDTO {
  clause?: ClauseDTO | null;
  depends_on?: string[];
  description: string;
  formatted: string;
  latex?: string | null;
  numeric?: string | null;
  provenance?: ProvenanceDTO | null;
  symbol: string;
  unit: string;
  value: number;
}

/** Un calcul de flexion **sur un projet**. Il ne nomme aucun référentiel. CE QU'IL NE PORTE PAS, ET POURQUOI CHAQUE ABSENCE COMPTE --------------------------------------------------------- ``project_id`` Il est dans le chemin. Le laisser aussi dans le corps donnerait deux sources pour une même question, et la note pourrait nommer un dossier autre que celui où elle est rangée. ``country``, ``region``, ``as_of`` Ils décident **quelle édition d'Annexe Nationale s'applique**, donc quelles valeurs entrent dans les formules. Ils sont figés sur le projet à sa création. Les accepter ici laissait — mesuré — un calcul français aboutir sur un projet belge, avec une ligne enregistrée qui se contredisait : ``request.country = FR`` et ``calculations.ndp_as_of`` repris du projet. ``Strict`` INTERDIT LES CHAMPS SUPPLÉMENTAIRES, si bien qu'un client qui envoie encore l'un des quatre reçoit un **422** — une réponse — plutôt qu'un champ silencieusement ignoré. Écraser aurait marché tant qu'une seule route existe ; refuser dit au client que son champ n'a pas d'effet. CE QU'IL PORTE, ET QUI EST BIEN À LUI -------------------------------------- La géométrie, les matériaux, la situation de projet, le moment, le ferraillage éventuellement retenu, la provenance des entrées, et ``strict_ndp``. Tout cela change d'un calcul à l'autre par nature. */
export interface CalculDeProjetRequest {
  /** Aire des barres réellement disposées. Omise, la vérification porte sur l'aire strictement requise. */
  A_s_provided?: QuantityDTO | null;
  /** Moment de calcul issu de la combinaison EN 1990 déterminante. Le moteur ne construit pas les combinaisons. */
  M_Ed: QuantityDTO;
  /** Repère de l'élément, tel qu'il apparaîtra sur la note. */
  element?: string;
  materials: MaterialsDTO;
  section: RectangularSectionDTO;
  situation?: DesignSituationDTO;
  /** Quand vrai, un paramètre national non confirmé provoque un refus. Exigé pour tout livrable destiné à être signé. */
  strict_ndp?: boolean;
}

/** Un calcul rouvert : les MÊMES entrées, les MÊMES résultats. ``request`` est la requête exacte reçue par le moteur, pas une reconstruction. ``inputs_hash`` en est l'empreinte, et permet à l'écran de dire « ce sont bien ces entrées-là » sans faire confiance au transport. ``ndp_snapshot`` est l'état du portillon normatif **au moment du calcul**. Il change quand une confirmation arrive ou est révoquée ; le relire aujourd'hui donnerait l'état d'aujourd'hui pour un calcul d'hier. */
export interface CalculEnregistre {
  calculation_id: string;
  created_at: string;
  /** Le build EXACT qui a produit ce calcul. La version seule ne désigne aucun code: plusieurs commits successifs la partagent. */
  engine_build_sha?: string | null;
  engine_version: string;
  /** Empreinte canonique de (requête, instantané NDP, moteur, build). Deux exécutions de même identité doivent rendre le même résultat. Distincte d'`inputs_hash`, qui n'empreinte que la requête. */
  execution_identity?: string | null;
  /** Empreinte de la REQUÊTE, et rien d'autre. Elle répond à « est-ce la même demande ? », pas à « obtiendra-t-on le même résultat ? » — cela dépend aussi du code et du référentiel, que porte `execution_identity`. */
  inputs_hash: string;
  journal?: unknown | null;
  /** « PROJET — NON SIGNABLE ». Présente uniquement quand des paramètres nationaux non confirmés ont pu servir. Bien plus forte que `notice`: celle-ci dit « pas encore signé », celle-là « pas signable du tout ». */
  mention?: string | null;
  /** La date de référence effectivement appliquée, reprise du projet. */
  ndp_as_of?: string | null;
  ndp_snapshot?: Record<string, unknown> | null;
  /** La mention obligatoire: ce document doit être vérifié et signé par un ingénieur habilité. Elle accompagne un calcul relu comme elle accompagne un calcul neuf. */
  notice: string;
  project_id: string;
  refusal?: Record<string, unknown> | null;
  request: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  status: string;
  strict_ndp: boolean;
  verifications?: (Record<string, unknown>)[];
}

/** Une ligne d'historique. Assez pour choisir, pas assez pour conclure. ``max_utilisation`` est ``None`` quand le calcul n'a produit aucune vérification — un refus, notamment. Le rendre à ``0.0`` ferait lire « largement vérifié » là où rien n'a été vérifié. */
export interface CalculResume {
  calculation_id: string;
  created_at: string;
  element?: string | null;
  engine_version: string;
  inputs_hash: string;
  max_utilisation?: number | null;
  /** 'succeeded' ou 'refused'. Un refus reste un refus dans l'historique: il n'est ni omis, ni dégradé en échec technique. */
  status: string;
  strict_ndp: boolean;
}

export interface CheckDTO {
  acting: string;
  clause: ClauseDTO;
  detail?: string | null;
  name: string;
  remedy?: string | null;
  resisting: string;
  status: CheckStatusDTO;
  /** E_d / R_d. Always reported, never just 'OK'. */
  utilisation: number;
}

export type CheckStatusDTO =
  | "pass"
  | "fail"
  | "not_applicable";

export interface ClauseDTO {
  cite: string;
  clause: string;
  equation?: string | null;
  national_note?: string | null;
  standard: string;
}

export type DesignSituationDTO =
  | "persistent"
  | "transient"
  | "accidental"
  | "seismic";

/** Input of the ULS bending verification of a rectangular section. */
export interface Ec2BeamFlexureRequest {
  /** Area of the bars actually detailed. When omitted, the ULS check is made against the exact required area and its utilisation is 1,000. */
  A_s_provided?: QuantityDTO | null;
  /** Design moment from the governing EN 1990 combination. The engine does not build combinations. */
  M_Ed: QuantityDTO;
  /** Project reference date (ISO 8601) used to select the edition of the National Annex in force. Pin it on a real project so the calculation stays reproducible after a newer edition is published. Defaults to today. */
  as_of?: string | null;
  country: "BE" | "FR" | "ES" | "DE";
  /** Element mark shown in the note. */
  element?: string;
  materials: MaterialsDTO;
  project_id: string;
  /** Origin of each input, keyed by symbol (b, h, d, M_Ed). Values extracted from a document must carry confirmed_by/confirmed_at. */
  provenance?: Record<string, ProvenanceDTO>;
  /** Sub-national region where it changes the parameters (Wallonie / Vlaanderen / Bruxelles, Land, Comunidad autonoma). */
  region?: string | null;
  section: RectangularSectionDTO;
  situation?: DesignSituationDTO;
  /** When true, an unverified National Annex parameter causes a refusal. Required for any deliverable intended to be signed; set false only for exploratory work. */
  strict_ndp?: boolean;
}

/** Output of a successful verification. A refusal is *not* represented here: it is returned as :class:`~eurostruct_engine.schemas.common.EngineErrorDTO` with HTTP 422, so a caller cannot mistake a refusal for a result. */
export interface Ec2BeamFlexureResponse {
  element: string;
  /** Stamped into the note de calcul and every drawing. */
  engine_version: string;
  journal: JournalDTO;
  ndp: NdpSummaryDTO;
  result: Ec2BeamFlexureResult;
  verification: VerificationReportDTO;
}

/** Numeric outcome. Every field is also reachable through the journal. */
export interface Ec2BeamFlexureResult {
  /** §9.2.1.1(3) */
  As_max: QuantityDTO;
  /** §9.2.1.1(1), eq. (9.1N) */
  As_min: QuantityDTO;
  As_provided: QuantityDTO;
  /** max(As_strength, As_min) */
  As_required: QuantityDTO;
  /** Area required by strength alone */
  As_strength: QuantityDTO;
  M_Rd: QuantityDTO;
  eps_s: number;
  mu: number;
  utilisation: number;
  /** Neutral axis depth */
  x: QuantityDTO;
  xi: number;
  xi_lim: number;
  /** Lever arm */
  z: QuantityDTO;
}

/** Verify the chosen bars, **then** draw them — never the reverse. WHY THE CALCULATION TRAVELS WITH THE DRAWING REQUEST ----------------------------------------------------- Measured on 30/08: the interface sent a hard-coded 300 x 500 to the drawing endpoint whatever section had just been calculated. The engineer received a plan of a beam that was never verified, carrying the mandatory notice and their own element mark. Nothing could catch it, because the drawing endpoint had no way to know what had been calculated: it was handed a geometry and drew it, correctly. Sending the **verified request itself** removes the gap by construction — the drawn section and the checked section are the same object, and no caller can hold two of them. ``A_s_provided`` is deliberately absent: it is **computed here** from the bars, so that no client has to, and so that none can claim an area its bars do not have. */
export interface Ec2BeamSectionRequest {
  calculation: Ec2BeamFlexureRequest;
  date?: string;
  exposure_class?: string;
  index?: string;
  /** Mention supplementaire portee au cartouche du dessin. */
  mention?: string;
  plot_scale?: number;
  reinforcement: ReinforcementChoiceDTO;
}

/** Une vérification complète **sur un projet**. Elle ne nomme aucun référentiel : voir le docstring du module. */
export interface Ec2BeamVerificationRequest {
  M_Ed: QuantityDTO;
  /** Moment sous combinaison caractéristique. Il majore M_qp par nature. */
  M_char: QuantityDTO;
  /** Moment sous combinaison quasi-permanente. */
  M_qp: QuantityDTO;
  V_Ed: QuantityDTO;
  /** Longueur d'ancrage réellement disponible. L'ingénieur seul connaît l'about dont il dispose ; sans elle, l'ancrage serait le seul chapitre sans verdict. */
  anchorage_available: QuantityDTO;
  b_eff_over_b_w?: number | null;
  bars: LongitudinalBarsDTO;
  bond_condition?: string;
  /** Inclinaison des bielles retenue par l'ingénieur. Une borne nationale peut la refuser, et c'est un refus juste. */
  cot_theta: number;
  cover: QuantityDTO;
  element?: string;
  exposure_class: string;
  geometry: BeamGeometryDTO;
  links: TransverseLinksDTO;
  materials: VerificationMaterialsDTO;
  /** Coefficient de fluage φ(∞,t0), §3.1.4. Fourni par l'ingénieur, jamais deviné : il dépend du rayon moyen, de l'humidité et de l'âge au chargement. */
  phi_creep: number;
  /** Quand vrai, un paramètre national non confirmé bloque AVANT le calcul, et rien n'est enregistré. */
  strict_ndp?: boolean;
  /** Ligne du Tableau 7.4N. Aucun défaut. */
  structural_system: string;
  /** Aucune géométrie ne le révèle : c'est une donnée. */
  supports_brittle_partitions?: boolean;
}

/** L'étude enregistrée, telle que le serveur la rend et la relit. */
export interface Ec2BeamVerificationResponse {
  bar_spacing: QuantityDTO;
  calculation_fingerprint: string;
  calculation_id: string;
  country: string;
  element: string;
  engine_build_sha: string;
  engine_version: string;
  engineering_inputs_hash: string;
  execution_identity: string;
  inputs?: Record<string, unknown>;
  is_exploratory: boolean;
  max_utilisation: number;
  may_be_finalised: boolean;
  mention?: string | null;
  ndp_as_of: string;
  ndp_snapshot_id: string;
  notice: string;
  preflight_ready: boolean;
  region: string | null;
  requires_additional_analysis: boolean;
  sections: SectionOutcomeDTO[];
  /** passed | failed | incomplete */
  status: string;
  strict_ndp: boolean;
}

/** A refusal. The API returns this with HTTP 422, never a partial result. */
export interface EngineErrorDTO {
  clause?: string | null;
  detail: string;
  /** Machine-readable class of refusal. */
  error: "out_of_validation_domain" | "national_annex_incomplete" | "unverified_national_parameter" | "deprecated_national_parameter" | "inconsistent_input" | "unit_error" | "reinforcement_not_verified";
  preflight?: PreflightReportDTO | null;
  what: string;
}

/** L'historique d'un projet, du plus récent au plus ancien. */
export interface HistoriqueCalculs {
  calculations: CalculResume[];
  project_id: string;
}

/** Une invitation, telle que le panneau d'administration la montre. NI LE SECRET NI SON EMPREINTE. Le premier n'existe plus ; la seconde suffirait à reconnaître un lien intercepté ailleurs, et n'aide en rien l'écran. */
export interface Invitation {
  accepted_at: string | null;
  created_at: string;
  display_name: string | null;
  expires_at: string;
  invitation_id: string;
  label: string | null;
  professional_id: string | null;
  revoked_at: string | null;
  role: string;
  /** pending | accepted | revoked | expired. Calculé par la base, pas par l'écran : deux horloges donneraient deux réponses. */
  state: string;
}

/** Ce que l'invité obtient : une organisation, et son rôle dedans. */
export interface InvitationAcceptee {
  member_role: string;
  organization_id: string;
  organization_name: string;
}

/** Ce qu'un owner ou un admin saisit pour accueillir quelqu'un. AUCUNE ADRESSE ÉLECTRONIQUE. Une invitation liée à une adresse ouvre l'énumération des comptes : « invitez untel@exemple.fr » répondrait différemment selon que le compte existe ou non, et l'on apprendrait qui travaille où. ``label`` est un aide-mémoire libre pour l'émetteur ; il n'entre dans aucune décision. */
export interface InvitationCreation {
  /** Le nom professionnel sous lequel l'invité signera. POSÉ PAR L'ORGANISATION, jamais par l'invité : quelqu'un qui choisirait lui-même ce nom pourrait attester sous celui d'un autre. */
  display_name?: string | null;
  /** Aide-mémoire libre, pour que l'émetteur s'y retrouve. N'entre dans aucune décision. */
  label?: string | null;
  professional_id?: string | null;
  /** Le rôle que l'invité aura. Un « admin » ne peut pas inviter un « owner » : il donnerait plus que son propre pouvoir. */
  role: string;
  /** Durée de validité du lien. Un lien qui n'expire jamais est un mot de passe permanent. */
  validity_days?: number;
}

/** La réponse à une émission — et le SEUL endroit où le secret apparaît. ``token`` N'EST PAS EN BASE. PostgreSQL n'en détient que le sha256 : une fuite de sauvegarde, un journal trop bavard ou une lecture accidentelle ne rendent aucun lien utilisable. En contrepartie, ce secret ne peut pas être réaffiché : il faut le copier maintenant, ou révoquer et réémettre. */
export interface InvitationEmise {
  expires_at: string;
  invitation_id: string;
  organization_id: string;
  role: string;
  /** Le secret du lien, en clair, UNE SEULE FOIS. Il n'existe nulle part ailleurs — ni en base, ni dans les journaux. */
  token: string;
}

/** Ce qu'un invité présente pour rejoindre un bureau. LE REFUS EST LE MÊME dans les quatre cas — inconnue, expirée, révoquée, déjà consommée. Distinguer « ce lien n'existe pas » de « ce lien a expiré » apprendrait à qui essaie des liens au hasard quand il a visé juste. */
export interface JetonInvitation {
  token: string;
}

export interface JournalDTO {
  clauses: string[];
  steps: CalcStepDTO[];
  title: string;
}

export interface ListeInvitations {
  invitations: Invitation[];
}

export interface ListeLivrables {
  deliverables?: Livrable[];
}

export interface ListeMembres {
  members: Membre[];
}

/** Les projets des organisations de l'appelant, et rien d'autre. */
export interface ListeProjets {
  projects: Projet[];
}

/** Un livrable, tel que la liste du projet le montre. ``state`` EST LA SEULE VÉRITÉ SUR L'ÉTAT. ``is_final`` en est dérivé en base et ne traverse pas jusqu'ici : deux champs pour un même fait finissent par se contredire, et c'est l'écran qui affiche le mauvais. */
export interface Livrable {
  calculation_id: string;
  deliverable_id: string;
  /** Le livrable dont celui-ci DÉRIVE, sans le remplacer. Distinct de `supersedes_id` : un indice remplace, un document émis atteste. Renseigné sur le document émis, qui référence la note dont l'empreinte est attestée. */
  derived_from_id?: string | null;
  engine_build_sha?: string | null;
  engine_version: string;
  execution_identity?: string | null;
  filename: string;
  generated_at: string;
  kind: string;
  last_reason?: string | null;
  media_type: string;
  revision: number;
  /** Empreinte des octets réellement enregistrés. La route de téléchargement la revérifie sur ce qu'elle sert. */
  sha256: string;
  size_bytes: number;
  /** brouillon (draft), en relecture (review), validé (validated), émis (final). */
  state: string;
  supersedes_id?: string | null;
  validated_at?: string | null;
  validation_id?: string | null;
  validator_name?: string | null;
  /** Le filigrane RÉELLEMENT apposé sur les octets. Il dit ce qui est vrai du document pour toujours — « PROJET — NON SIGNABLE » — et jamais son état de workflow, qui change. */
  watermark?: string | null;
}

/** Créer un brouillon **depuis un calcul déjà enregistré**. LE CONTENU EST PRODUIT SUR LE SERVEUR à partir des données gelées du calcul ; sa nature, son nom, ses octets, leur empreinte, leur taille, le contexte normatif, la version du moteur, le build et l'identité d'exécution sont tous dérivés. Le client n'en nomme aucun. ``kind`` N'EST PAS UN CHAMP. Le produit sait produire une note de calcul, et rien d'autre aujourd'hui. Offrir le choix entre huit natures de document dont six n'existent pas ferait promettre à l'écran des livrables qu'aucune route ne produit. ``format`` EST LA SEULE EXCEPTION, ET CE N'EST PAS UNE VALEUR DERIVEE. Le même calcul, les mêmes chiffres, la même mention obligatoire — seule la forme du fichier change. C'est un choix qui appartient au client : on lit une note à l'écran en HTML, on la joint à un dossier en PDF. Rien de ce que le document AFFIRME n'en dépend, et c'est ce qui distingue ce champ de ceux que la route refuse. */
export interface LivrableCreation {
  /** Le calcul enregistré dont ce livrable est tiré. Il doit appartenir au projet du chemin, avoir abouti, et porter une identité d'exécution vérifiable. */
  calculation_id: string;
  /** La forme du fichier produit. « html » est un document autonome qui s'ouvre hors ligne ; « pdf » est composé sans aucune date interne, afin que deux compositions du même calcul portent la même empreinte ; « dxf » est le plan de ferraillage, en R2018, ouvrable par tout logiciel de CAO — aucune licence AutoCAD n'est requise. */
  format?: "html" | "pdf" | "dxf";
  /** Obligatoire pour « dxf », refusé partout ailleurs. C'est le CHOIX DE L'INGÉNIEUR — nombre de barres, diamètre, enrobage, cadres — et c'est la seule chose que le client apporte au dessin : la section, les matériaux, l'effort et le référentiel sont relus dans le calcul gelé. `A_s_provided` n'y figure pas : le moteur le dérive des barres, si bien qu'aucun appelant ne peut annoncer une aire que son ferraillage n'a pas. */
  reinforcement?: ReinforcementChoiceDTO | null;
}

/** Un livrable, son contexte figé, son attestation et son histoire. L'HISTORIQUE VIENT DU MÊME APPEL QUE L'ÉTAT. Deux appels séparés pourraient tomber de part et d'autre d'une transition et montrer un état qui ne correspond pas à son journal. */
export interface LivrableDetail {
  calculation_id: string;
  deliverable_id: string;
  /** Le livrable dont celui-ci DÉRIVE, sans le remplacer. Distinct de `supersedes_id` : un indice remplace, un document émis atteste. Renseigné sur le document émis, qui référence la note dont l'empreinte est attestée. */
  derived_from_id?: string | null;
  engine_build_sha?: string | null;
  engine_version: string;
  execution_identity?: string | null;
  filename: string;
  generated_at: string;
  inputs_hash?: string | null;
  /** Le document émis produit par l'émission de CE livrable — un second PDF, immuable, qui porte l'attestation et référence l'original par son empreinte. Renseigné sur la note d'origine, jamais sur le document émis lui-même. */
  issued_deliverable_id?: string | null;
  kind: string;
  last_reason?: string | null;
  media_type: string;
  /** « PROJET — NON SIGNABLE », quand des paramètres nationaux non confirmés ont pu servir. */
  mention?: string | null;
  ndp_as_of?: string | null;
  /** La mention obligatoire: ce document doit être vérifié et signé par un ingénieur habilité. */
  notice: string;
  /** Numéro d'inscription à l'ordre professionnel, figé au moment de l'attestation depuis l'adhésion. */
  professional_id?: string | null;
  reservations?: string | null;
  revision: number;
  /** Empreinte des octets réellement enregistrés. La route de téléchargement la revérifie sur ce qu'elle sert. */
  sha256: string;
  size_bytes: number;
  /** brouillon (draft), en relecture (review), validé (validated), émis (final). */
  state: string;
  statement?: string | null;
  supersedes_id?: string | null;
  transitions?: Transition[];
  validated_at?: string | null;
  validation_id?: string | null;
  validator_name?: string | null;
  validator_role?: string | null;
  /** Le filigrane RÉELLEMENT apposé sur les octets. Il dit ce qui est vrai du document pour toujours — « PROJET — NON SIGNABLE » — et jamais son état de workflow, qui change. */
  watermark?: string | null;
}

/** Le lit tendu. ``A_s`` s'en DÉRIVE et ne se saisit jamais à côté. */
export interface LongitudinalBarsDTO {
  count: number;
  diameter: QuantityDTO;
}

export interface MaterialsDTO {
  /** EN 1992-1-1 Table 3.1 designation. */
  concrete_grade: string;
  /** Reinforcement designation. */
  steel_grade: string;
}

/** Une adhésion, telle que le panneau d'administration la montre. ``is_active = false`` NE FAIT PAS DISPARAÎTRE LA LIGNE, et c'est voulu depuis 0009 : une note de dix ans doit rester lisible et nommer son signataire. Ce qui disparaît, c'est l'accès. */
export interface Membre {
  created_at: string;
  deactivated_at: string | null;
  display_name: string | null;
  is_active: boolean;
  /** Vrai pour la ligne de l'appelant. L'écran s'en sert pour ne pas proposer des gestes que la base refuse de toute façon : on ne modifie pas sa propre adhésion. */
  is_me: boolean;
  professional_id: string | null;
  role: string;
  user_id: string;
}

/** Ce qu'un owner ou un admin change sur l'adhésion d'un collègue. LES CHAMPS ABSENTS NE SONT PAS TOUCHÉS. Envoyer ``role`` seul ne remet pas les noms à zéro : ``update_names`` doit être demandé explicitement, faute de quoi un formulaire partiel effacerait le nom sous lequel quelqu'un a signé. */
export interface MembreModification {
  display_name?: string | null;
  is_active?: boolean | null;
  professional_id?: string | null;
  role?: string | null;
  /** Sans lui, ``display_name`` et ``professional_id`` sont ignorés. Un formulaire partiel n'efface pas le nom sous lequel quelqu'un a signé. */
  update_names?: boolean;
}

/** One published National Annex document, at one edition. */
export interface NationalAnnexDTO {
  country_code: string;
  edition: string;
  effective_from: string;
  effective_to?: string | null;
  reference: string;
  source_official: string;
  source_url_or_doc_id?: string | null;
  standard: string;
}

/** One national parameter, at one version. Carries its own provenance so the note de calcul can print the annex reference, the edition and who checked it, next to the value. */
export interface NdpEntryDTO {
  clause: string;
  country_code: string;
  description: string;
  edition: string;
  effective_from: string;
  effective_to?: string | null;
  en_recommended?: number | null;
  key: string;
  national_annex_reference: string;
  notes?: string | null;
  parameter_name: string;
  parameter_value: number | null;
  part: string;
  /** sha256 of the deposited document the value was read from. */
  source_doc_id?: string | null;
  source_official: string;
  /** Page of that document, as printed. */
  source_page?: number | null;
  source_type: SourceTypeDTO;
  source_url_or_doc_id?: string | null;
  standard: string;
  standard_family: string;
  unit: string;
  validation_status: ValidationStatusDTO;
  variants?: ParameterVariantDTO[];
  verified_at?: string | null;
  verified_by?: string | null;
}

/** Printed verbatim in the 'referentiel applique' section of the note. */
export interface NdpSummaryDTO {
  annexes: NationalAnnexDTO[];
  /** Project reference date used to select the edition in force. */
  as_of: string;
  country: string;
  country_name: string;
  parameters: Record<string, NdpEntryDTO>;
  region?: string | null;
  regulatory_framework: RegulatoryFrameworkDTO;
  strict: boolean;
  /** Parameters not yet confirmed against the published National Annex. */
  unverified: string[];
}

/** Un bureau, tel que l'écran d'entrée le montre. */
export interface Organisation {
  country: "BE" | "FR" | "ES" | "DE";
  /** Le rôle de l'appelant DANS ce bureau. Dérivé de l'adhésion, jamais déclaré. */
  member_role: string;
  name: string;
  organization_id: string;
}

/** Ce qu'une personne saisit pour fonder son bureau. AUCUN CHAMP NE DÉSIGNE LE FONDATEUR. C'est l'appelant, dérivé du jeton : fonder au nom de quelqu'un d'autre n'a pas de sens, et l'accepter dans le corps ferait de l'appartenance une simple affirmation. */
export interface OrganisationCreation {
  country: "BE" | "FR" | "ES" | "DE";
  /** Le nom professionnel du fondateur dans ce bureau. Il figurera sur les attestations qu'il signera ; sans lui, la primitive d'attestation refuse. */
  display_name?: string | null;
  name: string;
  /** Numéro d'inscription à l'ordre ou à la chambre professionnelle. Il n'est vérifié par personne ici, et aucune valeur n'est inventée : il est reproduit tel quel. */
  professional_id?: string | null;
}

/** One branch of a parameter the National Annex makes conditional. Belgium's alpha_cc is 0,85 for axial force and bending, 1,0 otherwise. The frontend must never collapse this to one number for display without saying which case it shows. */
export interface ParameterVariantDTO {
  /** Which verification this branch applies to, matched exactly. */
  condition: string;
  /** What the annex says about this branch. */
  description: string;
  value: number;
}

/** Un paramètre qui empêche le calcul, et le module qui le réclame. */
export interface PreflightBlockerDTO {
  annex: string;
  clause: string;
  detail: string;
  module: string;
  parameter: string;
  reason: string;
}

/** Result of checking every required national parameter before running. Returned in full on refusal, so the user fixes the whole list in one pass. */
export interface PreflightReportDTO {
  as_of: string;
  blocking: BlockingParameterDTO[];
  country_code: string;
  ok: boolean;
  required: string[];
  strict: boolean;
}

/** Un projet, tel que l'atelier le montre. ``organization_name`` accompagne ``organization_id`` : un identifiant seul obligerait l'écran à un second appel pour afficher « Bureau A », et c'est ce genre de second appel qui finit par ne jamais être fait. */
export interface Projet {
  /** Combien de calculs sont enregistrés sur ce projet. */
  calculation_count: number;
  country: "BE" | "FR" | "ES" | "DE";
  created_at: string;
  /** Faux quand l'accès à cette organisation a été révoqué. Le projet reste lisible — la trace des signatures passées doit le rester — et toute action est fermée. */
  member_active?: boolean;
  /** Le nom de l'appelant tel que l'organisation l'enregistre. C'est celui qui figurera sur une attestation: son absence se constate ici plutôt qu'au moment de signer. */
  member_name?: string | null;
  /** Le rôle de l'appelant dans l'organisation de CE projet. Dérivé de l'adhésion côté serveur. L'écran s'en sert pour montrer ou expliquer une action; il ne décide de rien — la frontière est dans PostgreSQL. */
  member_role: string;
  name: string;
  /** Date de référence du projet (ISO 8601). Elle résout l'édition d'Annexe Nationale en vigueur, norme par norme. Ce n'est pas la date du calcul. */
  ndp_as_of: string;
  organization_id: string;
  organization_name: string;
  project_id: string;
  reference?: string | null;
  /** Région sous-nationale quand elle change les paramètres (Wallonie / Vlaanderen / Bruxelles, Land, Comunidad autónoma). Figée à la création, comme le pays et la date. */
  region?: string | null;
}

/** Ce qu'un ingénieur saisit pour ouvrir un projet. ``ndp_as_of`` N'EST PAS DÉCORATIVE. Elle résout l'édition d'Annexe Nationale en vigueur, norme par norme, et se fige à la création : sans elle, le référentiel dépendrait de la date à laquelle le calcul est lancé — c'est-à-dire du hasard. */
export interface ProjetCreation {
  country: "BE" | "FR" | "ES" | "DE";
  name: string;
  /** Date de référence, ISO 8601 (AAAA-MM-JJ). Elle résout l'édition d'Annexe Nationale en vigueur et se fige à la création du projet. */
  ndp_as_of: string;
  /** Facultatif, et jamais cru sur parole: la base le confronte aux appartenances. Nécessaire uniquement quand l'appelant appartient à plusieurs organisations. */
  organization_id?: string | null;
  reference?: string | null;
  /** Région sous-nationale, quand elle change les paramètres nationaux. Elle se fige à la création avec le pays et la date: un calcul ne pourra plus en désigner une autre. */
  region?: string | null;
}

/** Where a value came from. ``document_extraction`` values must already have been confirmed by a human before the orchestrator submits them: ``confirmed_by`` and ``confirmed_at`` are how the engine's output can state that the gate was passed. */
export interface ProvenanceDTO {
  /** [x0, y0, x1, y1] in PDF points, so the UI can highlight the source. */
  bbox?: [number, number, number, number] | null;
  confirmed_at?: string | null;
  confirmed_by?: string | null;
  detail: string;
  document_id?: string | null;
  kind: ProvenanceKindDTO;
  ndp_key?: string | null;
  page?: number | null;
}

export type ProvenanceKindDTO =
  | "user_input"
  | "document_extraction"
  | "national_annex"
  | "standard_constant"
  | "derived";

/** A physical quantity with an explicit unit. */
export interface QuantityDTO {
  /** Pint-parsable unit, e.g. 'mm', 'kN*m', 'MPa', 'dimensionless'. */
  unit: string;
  value: number;
}

/** One line of the nomenclature — section 7.2. */
export interface RebarScheduleRowDTO {
  comment?: string;
  count: number;
  diameter_mm: number;
  mark: string;
  mass_kg: number | null;
  /** Shape code per EN ISO 3766 */
  shape_code: string;
  total_length_mm: number | null;
  unit_length_mm: number | null;
}

export interface RectangularSectionDTO {
  /** Width */
  b: QuantityDTO;
  /** Effective depth to the tension reinforcement */
  d: QuantityDTO;
  /** Overall depth */
  h: QuantityDTO;
}

/** What is legally binding in the country — not always the Eurocode. Interdiction 4: a Spanish project must state that the Código Estructural, the CTE and NCSE-02 are the enforceable reference. */
export interface RegulatoryFrameworkDTO {
  binding_reference: string;
  eurocode_status: string;
  notes?: string[];
  verification_regime: string;
}

/** The bars the engineer chose. Never deduced from the calculation. ``As_required`` says how much steel is needed; it says nothing about how many bars, of which diameter, arranged how. That choice is the engineer's, and this is where it enters — separately from the geometry, which comes from the calculation that was verified. */
export interface ReinforcementChoiceDTO {
  bottom: BarRowDTO[];
  /** Nominal cover c_nom, mm */
  cover: number;
  /** Link diameter, mm */
  link_diameter: number;
  link_mark?: string;
  link_spacing?: number | null;
  top?: BarRowDTO[];
}

/** Renvoyer une pièce en relecture vers le brouillon, **avec un motif**. LE MOTIF EST OBLIGATOIRE, ET LA BASE LE REFUSE VIDE ELLE AUSSI. Celui qui reprend le document doit savoir ce qui lui est reproché ; un retour muet est une décision qu'on ne peut pas relire six mois plus tard. */
export interface RetourAuBrouillon {
  /** Ce qui est reproché à la pièce. Repris dans l'historique des transitions et affiché à celui qui la reprend. */
  reason: string;
}

/** Le verdict d'un des cinq chapitres. */
export interface SectionOutcomeDTO {
  basis: string;
  key: string;
  /** Code machine quand la cause est une dépendance, p. ex. « prerequisite_failed:flexure ». */
  reason?: string | null;
  remedy?: string | null;
  /** passed | failed | additional_analysis_required | not_evaluated. Une section non évaluée n'est JAMAIS conforme. */
  status: string;
  title: string;
  /** Absent quand la section n'a pas tourné : un taux suppose un calcul. */
  utilisation?: number | null;
}

export type SourceTypeDTO =
  | "national_annex"
  | "en_recommended"
  | "national_regulation";

/** Un pas dans le parcours de relecture, horodaté et attribué. */
export interface Transition {
  /** Qui a provoqué la transition. Dérivé de la session, jamais du corps de la requête. */
  actor_id?: string | null;
  /** L'état quitté. Absent pour la création du brouillon. */
  from_state?: string | null;
  occurred_at: string;
  reason?: string | null;
  to_state: string;
}

/** Les cadres. ``A_sw`` se dérive des branches et du diamètre. */
export interface TransverseLinksDTO {
  diameter: QuantityDTO;
  legs: number;
  spacing: QuantityDTO;
}

/** How far a national value has been verified — see TICKET 1.1. */
export type ValidationStatusDTO =
  | "confirmed"
  | "pending_verification"
  | "deprecated"
  | "not_representable";

export interface VerificationMaterialsDTO {
  concrete_grade: string;
  steel_grade: string;
}

export interface VerificationReportDTO {
  checks: CheckDTO[];
  element: string;
  max_utilisation: number;
  passed: boolean;
}
