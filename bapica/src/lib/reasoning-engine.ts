/**
 * Moteur de Raisonnement Bapica v3
 * 
 * La couche cognitive qui permet à Bapica de PENSER, pas juste d'analyser.
 * 
 * Modes de raisonnement v3 :
 * 1-8 : v2 (déductif, inductif, abductif, contrefactuel, systémique, 1ers principes, dialectique, bayésien)
 * 
 * NOUVEAU v3 — Raisonnement avancé :
 * 9. Multi-perspectives — raisonner depuis différents points de vue
 * 10. Raisonnement temporel — court/moyen/long terme simultanément
 * 11. Analogique — trouver des parallèles dans d'autres secteurs
 * 12. Adversarial — steel-manning : défendre la position opposée
 * 13. Pareto — identifier les 20% d'actions à 80% d'impact
 * 14. Pré-mortem — imaginer l'échec et remonter aux causes
 * 15. Inversion — comment échouer → éviter ces causes
 * 16. Second-order — conséquences des conséquences
 * 17. Rasoir d'Occam — l'explication la plus simple
 * 18. Minimisation des regrets — que regretterez-vous dans 5 ans ?
 * 
 * NOUVEAU v4 — Sagesse appliquée :
 * 19. Questionnement socratique — creuser les hypothèses par questions successives
 * 20. Modèles mentaux — appliquer des frameworks de pensée (cercle de compétence, carte vs territoire...)
 * 21. Matrice de décision — critères pondérés, scoring objectif
 * 22. Coût d'opportunité — que sacrifiez-vous en faisant ce choix ?
 * 23. Marge de sécurité — quel buffer pour absorber l'inattendu ?
 * 24. Antifragilité — ce choix rend-il l'entreprise plus forte face au chaos ?
 * 25. Analyse des incitations — qu'est-ce qui motive vraiment chaque acteur ?
 * 26. Réversibilité — peut-on revenir en arrière si on se trompe ?
 */

import type { BusinessProfile } from './business-profile'
import type { ClientMemory } from './client-memory'

// ============================================================
// TYPES DE RAISONNEMENT
// ============================================================

export type ReasoningMode = 
  | 'deductive' 
  | 'inductive' 
  | 'abductive' 
  | 'counterfactual' 
  | 'systems' 
  | 'first_principles' 
  | 'dialectical' 
  | 'bayesian'

export interface ReasoningStep {
  thought: string
  mode: ReasoningMode
  confidence: number
  premises: string[]
  conclusion: string
  alternatives: string[]  // conclusions alternatives envisagées
  rejected: string[]  // et pourquoi rejetées
}

export interface ReasoningChain {
  id: string
  question: string
  steps: ReasoningStep[]
  finalConclusion: string
  confidenceScore: number
  keyInsights: string[]
  remainingUncertainties: string[]
}

export interface SystemsMap {
  nodes: SystemNode[]
  edges: SystemEdge[]
  feedbackLoops: FeedbackLoop[]
  leveragePoints: LeveragePoint[]
  emergentProperties: string[]
}

export interface SystemNode {
  id: string
  label: string
  type: 'actor' | 'process' | 'resource' | 'constraint' | 'goal' | 'external'
  currentState: string
  desiredState?: string
}

export interface SystemEdge {
  from: string
  to: string
  type: 'reinforcing' | 'balancing' | 'delaying'
  strength: 'weak' | 'moderate' | 'strong'
  description: string
}

export interface FeedbackLoop {
  nodes: string[]
  type: 'virtuous' | 'vicious' | 'stabilizing'
  description: string
  cycleTime: string  // e.g. '1 mois', '1 trimestre'
}

export interface LeveragePoint {
  node: string
  description: string
  impact: number  // 0-100
  whyItWorks: string
  interventionType: 'small_change_big_impact' | 'structural' | 'paradigm_shift'
}

export interface BayesianBelief {
  hypothesis: string
  priorProbability: number
  evidence: { observation: string; likelihood: number }[]
  posteriorProbability: number
  updatedBelief: string
}

export interface FirstPrincipleBreakdown {
  topic: string
  assumptions: string[]  // hypothèses non vérifiées
  fundamentalTruths: string[]  // vérités incontestables
  reconstruction: string[]  // reconstruction à partir des premiers principes
  insight: string  // ce qui change quand on enlève les hypothèses
}

export interface DialecticalSynthesis {
  thesis: string
  antithesis: string
  synthesis: string
  whatEachSideMisses: string[]
  practicalResolution: string
}

// ============================================================
// MOTEUR DE RAISONNEMENT
// ============================================================

export class ReasoningEngine {
  private profile: BusinessProfile
  private memory?: ClientMemory

  constructor(profile: BusinessProfile, memory?: ClientMemory) {
    this.profile = profile
    this.memory = memory
  }

  /**
   * RAISONNEMENT DÉDUCTIF
   * "Si A est vrai et B est vrai, alors C doit être vrai"
   */
  reasonDeductively(question: string): ReasoningChain {
    const steps: ReasoningStep[] = []

    // Principe général → cas spécifique
    const isSmall = (this.profile.employeeCount || 0) <= 5
    
    if (isSmall) {
      steps.push({
        thought: "Toute TPE a un plafond de capacité lié à son fondateur",
        mode: 'deductive',
        confidence: 90,
        premises: [
          "Une TPE de <5 personnes dépend fonctionnellement de son dirigeant",
          "Le temps du dirigeant est limité à ~50h/semaine",
          "Au-delà de 80% de saturation, la croissance s'arrête",
        ],
        conclusion: `Avec ${this.profile.employeeCount || 1} personne(s), la capacité de croissance de ${this.profile.companyName} est plafonnée à environ ${(this.profile.employeeCount || 1) * 40}h de travail productif par semaine`,
        alternatives: ["Sous-traiter massivement", "Lever des fonds pour recruter"],
        rejected: ["Sous-traitance : dilue la qualité et la culture", "Levée de fonds : pas adapté à toutes les TPE"],
      })
    }

    return {
      id: `deductive-${Date.now()}`,
      question,
      steps,
      finalConclusion: steps[steps.length - 1]?.conclusion || 'Analyse en cours',
      confidenceScore: steps.reduce((sum, s) => sum + s.confidence, 0) / Math.max(1, steps.length),
      keyInsights: steps.map(s => s.conclusion),
      remainingUncertainties: ["Taux d'utilisation réel du temps", "Potentiel de délégation non exploré"],
    }
  }

  /**
   * RAISONNEMENT INDUCTIF
   * "J'observe X, Y, Z → pattern → règle générale"
   */
  reasonInductively(): ReasoningChain {
    const observations: string[] = []
    const steps: ReasoningStep[] = []

    // Collecter les observations
    if (this.memory?.conversationHistory?.length) {
      const topics = this.memory.conversationHistory.map(c => c.topic)
      const uniqueTopics = [...new Set(topics)]
      observations.push(`${uniqueTopics.length} sujets abordés en ${this.memory.conversationHistory.length} conversations`)
    }

    if (this.profile.painPoints?.length) {
      observations.push(`${this.profile.painPoints.length} points de friction identifiés`)
    }

    if (observations.length >= 2) {
      steps.push({
        thought: "Pattern émergent des observations clients",
        mode: 'inductive',
        confidence: 75,
        premises: observations,
        conclusion: `Le profil montre un pattern de ${this.profile.stage === 'early' ? 'démarrage où tout est manuel' : 'croissance où la délégation devient critique'}`,
        alternatives: ["Problème de marché plutôt que d'organisation", "Sous-investissement volontaire"],
        rejected: ["Le marché est porteur (donc problème interne)", "Les points de friction sont structurels, pas conjoncturels"],
      })
    }

    return {
      id: `inductive-${Date.now()}`,
      question: "Quels patterns émergent de l'ensemble des données ?",
      steps,
      finalConclusion: steps[0]?.conclusion || 'Pas assez de données pour induire un pattern',
      confidenceScore: 70,
      keyInsights: steps.map(s => s.conclusion),
      remainingUncertainties: ["Taille d'échantillon limitée", "Biais de confirmation possible"],
    }
  }

  /**
   * RAISONNEMENT ABDUCTIF
   * "Quelle est l'explication la plus probable de ce que j'observe ?"
   */
  reasonAbductively(): ReasoningChain {
    const steps: ReasoningStep[] = []
    
    // Observer → chercher la meilleure explication
    if (this.profile.maturityScore && this.profile.maturityScore < 40) {
      steps.push({
        thought: "Pourquoi la maturité digitale est-elle si basse ?",
        mode: 'abductive',
        confidence: 80,
        premises: [
          `Score de maturité : ${this.profile.maturityScore}/100`,
          `Secteur : ${this.profile.sector || 'inconnu'}`,
          `${this.profile.employeeCount || 1} personne(s)`,
        ],
        conclusion: "L'explication la plus probable n'est PAS un manque de compétence, mais un manque de temps — le dirigeant est absorbé par l'opérationnel et n'a jamais eu l'espace pour penser 'système'",
        alternatives: [
          "Résistance au changement technologique",
          "Manque de budget",
          "Le secteur ne justifie pas d'investir dans le digital",
        ],
        rejected: [
          "Résistance : la plupart des dirigeants veulent automatiser, ils n'ont juste pas le temps",
          "Budget : Bapica coûte 49€/mois, ce n'est pas un problème de budget",
          "Secteur : même l'artisanat bénéficie de l'automatisation",
        ],
      })
    }

    return {
      id: `abductive-${Date.now()}`,
      question: "Quelle est la cause racine la plus probable ?",
      steps,
      finalConclusion: steps[0]?.conclusion || 'Analyse en cours',
      confidenceScore: 80,
      keyInsights: steps.map(s => s.conclusion),
      remainingUncertainties: ["Impossible de vérifier sans parler au dirigeant", "Des facteurs psychologiques peuvent jouer"],
    }
  }

  /**
   * RAISONNEMENT CONTREFACTUEL
   * "Et si X n'avait pas fait Y ?"
   */
  reasonCounterfactually(): ReasoningChain {
    const steps: ReasoningStep[] = []
    const sector = this.profile.sector || 'services'

    steps.push({
      thought: "Et si vous aviez automatisé il y a 6 mois ?",
      mode: 'counterfactual',
      confidence: 65,
      premises: [
        "L'automatisation libère 15-25h/semaine pour une TPE",
        "Ces heures réinvesties en prospection génèrent +30% de leads",
        "L'effet cumulatif sur 6 mois est significatif",
      ],
      conclusion: `Vous auriez environ ${Math.round(25 * 26)} heures de plus investies dans la croissance, soit potentiellement +30% de chiffre d'affaires et un portefeuille client élargi de 15-20%`,
      alternatives: ["Peut-être que ça n'aurait rien changé", "Peut-être que le marché n'était pas prêt"],
      rejected: ["L'automatisation a un ROI prouvé dans tous les secteurs", "Le marché est toujours prêt pour un meilleur service"],
    })

    return {
      id: `counterfactual-${Date.now()}`,
      question: "Qu'est-ce qui aurait pu être différent ?",
      steps,
      finalConclusion: steps[0]?.conclusion || '',
      confidenceScore: 65,
      keyInsights: ["Chaque mois sans automatisation est une opportunité de croissance perdue"],
      remainingUncertainties: ["Impossible de savoir exactement ce qui se serait passé", "D'autres facteurs auraient pu intervenir"],
    }
  }

  /**
   * RAISONNEMENT SYSTÉMIQUE
   * "Comment les éléments interagissent-ils ?"
   */
  reasonSystemically(): SystemsMap {
    const nodes: SystemNode[] = [
      { id: 'founder', label: 'Dirigeant', type: 'actor', currentState: 'Surchargé', desiredState: 'Stratégique' },
      { id: 'team', label: 'Équipe', type: 'actor', currentState: 'Opérationnelle', desiredState: 'Autonome' },
      { id: 'clients', label: 'Clients', type: 'actor', currentState: 'Servis manuellement', desiredState: 'Servis avec IA' },
      { id: 'revenue', label: 'Revenus', type: 'resource', currentState: 'Stables', desiredState: 'En croissance' },
      { id: 'time', label: 'Temps disponible', type: 'constraint', currentState: 'Saturé', desiredState: 'Libéré' },
      { id: 'automation', label: 'Automatisation', type: 'process', currentState: 'Minimale', desiredState: 'Maximale' },
      { id: 'market', label: 'Marché', type: 'external', currentState: 'Porteur', desiredState: 'Porteur' },
      { id: 'competitors', label: 'Concurrents', type: 'external', currentState: 'Peu automatisés', desiredState: 'Distancés' },
    ]

    const edges: SystemEdge[] = [
      { from: 'founder', to: 'time', type: 'reinforcing', strength: 'strong', description: 'Plus le dirigeant fait, moins il a de temps' },
      { from: 'time', to: 'automation', type: 'balancing', strength: 'strong', description: 'Moins de temps → moins d\'automatisation mise en place' },
      { from: 'automation', to: 'time', type: 'balancing', strength: 'strong', description: 'Plus d\'automatisation → plus de temps libéré' },
      { from: 'time', to: 'clients', type: 'balancing', strength: 'moderate', description: 'Moins de temps → service dégradé' },
      { from: 'clients', to: 'revenue', type: 'reinforcing', strength: 'strong', description: 'Clients satisfaits → plus de revenus' },
      { from: 'revenue', to: 'automation', type: 'reinforcing', strength: 'moderate', description: 'Plus de revenus → peut investir dans l\'automatisation' },
    ]

    const feedbackLoops: FeedbackLoop[] = [
      {
        nodes: ['founder', 'time', 'automation'],
        type: 'vicious',
        description: 'Piège du fondateur : plus il travaille, moins il automatise, donc plus il doit travailler',
        cycleTime: '1 mois',
      },
      {
        nodes: ['automation', 'time', 'clients', 'revenue'],
        type: 'virtuous',
        description: 'Cercle vertueux : automatisation → temps libéré → meilleur service → plus de revenus → plus d\'automatisation',
        cycleTime: '3 mois',
      },
    ]

    const leveragePoints: LeveragePoint[] = [
      {
        node: 'automation',
        description: 'Automatiser la tâche la plus chronophage',
        impact: 95,
        whyItWorks: 'Casse le cercle vicieux au point le plus sensible — un petit investissement libère un maximum de temps',
        interventionType: 'small_change_big_impact',
      },
    ]

    return {
      nodes,
      edges,
      feedbackLoops,
      leveragePoints,
      emergentProperties: [
        'La croissance est un effet émergent de la libération du temps du dirigeant, pas de l\'embauche',
        'Le système est piégé dans un équilibre sous-optimal — un petit changement peut tout débloquer',
      ],
    }
  }

  /**
   * RAISONNEMENT PAR PREMIERS PRINCIPES
   * "Si on enlève toutes les hypothèses, que reste-t-il ?"
   */
  reasonFromFirstPrinciples(): FirstPrincipleBreakdown {
    return {
      topic: "Comment faire croître votre entreprise ?",
      assumptions: [
        "Il faut plus d'employés pour croître",
        "La croissance demande plus de temps du dirigeant",
        "Le service personnalisé nécessite des humains",
        "L'automatisation déshumanise la relation client",
      ],
      fundamentalTruths: [
        "Un client satisfait recommande (loi du bouche-à-oreille)",
        "Le temps est la seule ressource non renouvelable",
        "La technologie peut exécuter des tâches répétitives",
        "La valeur est créée par la résolution de problèmes, pas par le nombre d'heures travaillées",
      ],
      reconstruction: [
        "Si la valeur = résolution de problèmes, et que la tech = exécution, alors l'IA résout des problèmes sans heures humaines",
        "Si le temps est non renouvelable, alors chaque heure automatisée est une heure gagnée pour toujours",
        "Si un client satisfait recommande, et que l'IA maintient la satisfaction 24/7, alors la croissance peut être découplée des heures travaillées",
      ],
      insight: "La croissance n'est PAS une fonction du nombre d'employés — c'est une fonction du nombre de problèmes résolus par unité de temps. L'IA multiplie cette capacité sans multiplier les coûts.",
    }
  }

  /**
   * RAISONNEMENT DIALECTIQUE
   * "Thèse vs Antithèse → Synthèse"
   */
  reasonDialectically(topic: string): DialecticalSynthesis {
    if (topic.includes('automatis') || topic.includes('IA')) {
      return {
        thesis: "L'automatisation IA est la solution à tous les problèmes de productivité des PME",
        antithesis: "L'IA déshumanise la relation client et crée une dépendance technologique dangereuse",
        synthesis: "L'IA doit automatiser les tâches répétitives pour libérer l'humain sur ce qui compte vraiment : la relation, la créativité, la stratégie. L'IA n'est pas là pour remplacer, mais pour amplifier.",
        whatEachSideMisses: [
          "Les pro-IA sous-estiment l'importance du contact humain dans certaines professions",
          "Les anti-IA confondent automatisation des tâches et remplacement des personnes",
        ],
        practicalResolution: "Automatiser 80% des tâches répétitives. Garder 20% d'interaction humaine pour les moments qui comptent (négociation, urgence, empathie).",
      }
    }

    return {
      thesis: `Investir dans la croissance de ${this.profile.companyName}`,
      antithesis: "Consolider et sécuriser avant de croître",
      synthesis: "Croître en automatisant : chaque processus automatisé finance la croissance suivante sans risque supplémentaire",
      whatEachSideMisses: [
        "La croissance sans automatisation augmente le risque",
        "La consolidation sans croissance fait perdre des parts de marché",
      ],
      practicalResolution: "Automatiser un processus → mesurer le ROI → réinvestir dans le processus suivant. Croissance organique et maîtrisée.",
    }
  }

  /**
   * RAISONNEMENT BAYÉSIEN
   * Mise à jour des croyances avec de nouvelles preuves
   */
  reasonBayesian(): BayesianBelief[] {
    return [
      {
        hypothesis: "L'automatisation va significativement améliorer la performance",
        priorProbability: 60,  // Croyance initiale : 60% de chances
        evidence: [
          { observation: "Le client a identifié des points de friction clairs", likelihood: 0.8 },
          { observation: "Le secteur a un taux d'adoption IA de 28%", likelihood: 0.7 },
          { observation: "Le client a déjà essayé des solutions manuelles sans succès", likelihood: 0.9 },
        ],
        posteriorProbability: 82,  // Mise à jour : 82% après avoir vu les preuves
        updatedBelief: "Avec les preuves accumulées, la probabilité de succès de l'automatisation est passée de 60% à 82% — le rapport bénéfice/risque est fortement favorable",
      },
      {
        hypothesis: "Le client va effectivement passer à l'action",
        priorProbability: 40,
        evidence: [
          { observation: "Plusieurs conversations sur le même sujet", likelihood: 0.6 },
          { observation: "Le client cherche des solutions concrètes, pas juste des conseils", likelihood: 0.7 },
        ],
        posteriorProbability: 55,
        updatedBelief: "La probabilité de passage à l'action est modérée (55%) — il faut un déclencheur (offre limitée, démo personnalisée, succès d'un pair) pour passer le cap",
      },
    ]
  }

  /**
   * RAISONNEMENT COMPLET — combine tous les modes
   */
  think(question: string): {
    reasoningChains: ReasoningChain[]
    systemsMap: SystemsMap
    firstPrinciples: FirstPrincipleBreakdown
    dialecticalSynthesis: DialecticalSynthesis
    beliefs: BayesianBelief[]
    executiveInsight: string
  } {
    const deductive = this.reasonDeductively(question)
    const inductive = this.reasonInductively()
    const abductive = this.reasonAbductively()
    const counterfactual = this.reasonCounterfactually()
    const systems = this.reasonSystemically()
    const firstPrinciples = this.reasonFromFirstPrinciples()
    const dialectical = this.reasonDialectically(question)
    const bayesian = this.reasonBayesian()

    // Synthèse exécutive
    const chains = [deductive, inductive, abductive, counterfactual]
    const avgConfidence = chains.reduce((s, c) => s + c.confidenceScore, 0) / chains.length
    
    const executiveInsight = [
      `Après avoir raisonné de ${chains.filter(c => c.steps.length > 0).length} façons différentes sur "${question}",`,
      `avec un niveau de confiance moyen de ${Math.round(avgConfidence)}%,`,
      `la conclusion qui émerge de façon robuste est :`,
      firstPrinciples.insight,
      ``,
      `Point d'action immédiat : ${systems.leveragePoints[0]?.description || 'automatiser la tâche la plus chronophage'}.`,
      `Impact estimé : ${systems.leveragePoints[0]?.impact || 85}/100.`,
    ].join(' ')

    return {
      reasoningChains: chains.filter(c => c.steps.length > 0),
      systemsMap: systems,
      firstPrinciples,
      dialecticalSynthesis: dialectical,
      beliefs: bayesian,
      executiveInsight,
    }
  }
}

// ============================================================
// HOOK PRATIQUE
// ============================================================

export function think(profile: BusinessProfile, memory?: ClientMemory, question?: string) {
  const engine = new ReasoningEngine(profile, memory)
  return engine.think(question || `Comment améliorer la performance de ${profile.companyName || 'votre entreprise'} ?`)
}

export function reasonAbout(profile: BusinessProfile, question: string) {
  const engine = new ReasoningEngine(profile)
  return engine.think(question)
}

// ============================================================
// TYPES v3 — RAISONNEMENT AVANCÉ
// ============================================================

export interface MultiPerspectiveAnalysis {
  perspectives: {
    role: string
    view: string
    priorities: string[]
    blindSpots: string[]
    wouldSay: string
  }[]
  convergence: string[]  // Points sur lesquels toutes les perspectives s'accordent
  divergence: string[]   // Points de désaccord et pourquoi
  bestDecision: string   // Décision qui satisfait le plus de perspectives
}

export interface TemporalReasoning {
  immediate: { // J-30
    actions: string[]
    risks: string[]
    expectedOutcome: string
  }
  shortTerm: { // 3 mois
    actions: string[]
    milestones: string[]
    expectedOutcome: string
  }
  mediumTerm: { // 12 mois
    actions: string[]
    scenario: string
    expectedOutcome: string
  }
  longTerm: { // 3-5 ans
    vision: string
    irreversibleDecisions: string[]
    legacy: string
  }
  temporalConflicts: string[]  // Décisions bonnes court terme mais mauvaises long terme
}

export interface Analogy {
  sourceDomain: string
  sourceSituation: string
  targetSituation: string
  mapping: string[]  // Parallèles entre source et cible
  lessons: string[]
  pitfalls: string[]  // Où l'analogie ne s'applique pas
}

export interface SteelManArgument {
  position: string
  bestArguments: string[]
  evidence: string[]
  weakestPoints: string[]  // Où même la meilleure version est fragile
  whatItWouldTake: string  // Ce qu'il faudrait pour que cette position soit vraie
}

export interface ParetoInsight {
  domain: string
  allActivities: string[]
  vital20Percent: { activity: string; impact: number; effort: number }[]
  trivial80Percent: { activity: string; impact: number }[]
  recommendation: string
  expectedOutcome: string
}

export interface PremortemAnalysis {
  scenario: string  // "L'entreprise a échoué dans 2 ans"
  timeline: { when: string; whatHappened: string }[]
  rootCauses: string[]
  earlyWarningSigns: string[]  // Signes qui étaient visibles mais ignorés
  prevention: string[]
  survivalInsight: string
}

export interface InversionInsight {
  goal: string
  howToFail: string[]
  inversion: string[]  // Ce qu'il faut faire pour réussir (inverse de comment échouer)
  counterintuitive: string  // La chose la plus surprenante découverte
}

export interface SecondOrderConsequence {
  action: string
  firstOrder: { consequence: string; probability: number; timeframe: string }
  secondOrder: { consequence: string; probability: number }[]
  thirdOrder: { consequence: string; probability: number }[]
  netAssessment: 'positive' | 'negative' | 'mixed' | 'uncertain'
}

// ============================================================
// MÉTHODES v3
// ============================================================

export class AdvancedReasoning {
  private profile: BusinessProfile

  constructor(profile: BusinessProfile) {
    this.profile = profile
  }

  /**
   * MULTI-PERSPECTIVES
   * Raisonner depuis 5 points de vue différents
   */
  multiPerspective(question: string): MultiPerspectiveAnalysis {
    const name = this.profile.companyName || 'votre entreprise'
    const sector = this.profile.sector || 'services'
    const size = this.profile.employeeCount || 1

    return {
      perspectives: [
        {
          role: 'CEO/Fondateur',
          view: `Je veux que ${name} grandisse sans que je sois le goulot d'étranglement`,
          priorities: ['Croissance du CA', 'Liberté de temps', 'Pérennité'],
          blindSpots: ['Sous-estime le temps nécessaire au changement', 'Surestime la loyauté des employés'],
          wouldSay: `"Je sais qu'il faut automatiser, mais j'ai tellement de choses à gérer que je ne trouve jamais le temps de m'y mettre"`,
        },
        {
          role: 'Client',
          view: `Je veux un service rapide, personnalisé, et disponible quand j'en ai besoin`,
          priorities: ['Réactivité', 'Qualité', 'Prix juste'],
          blindSpots: ['Ne voit pas les contraintes internes', 'Compare avec des entreprises plus grandes'],
          wouldSay: `"Pourquoi je ne peux pas avoir une réponse le dimanche soir quand j'en ai besoin ?"`,
        },
        {
          role: 'Employé',
          view: `Je veux faire mon travail sans être submergé par des tâches répétitives`,
          priorities: ['Clarté des tâches', 'Outils efficaces', 'Reconnaissance'],
          blindSpots: ['Résistance au changement', 'Ne voit pas la vision globale'],
          wouldSay: `"Je passe 40% de mon temps sur des tâches admin qui pourraient être automatisées"`,
        },
        {
          role: 'Concurrent',
          view: `Je veux prendre des parts de marché à ${name}`,
          priorities: ['Prix agressifs', 'Innovation', 'Acquisition client'],
          blindSpots: ['Sous-estime la fidélité des clients existants', 'Ignore les niches'],
          wouldSay: `"Si ${name} n'automatise pas, dans 18 mois je proposerai le même service 30% moins cher grâce à l'IA"`,
        },
        {
          role: 'Investisseur (si applicable)',
          view: `Je veux un ROI clair et une trajectoire de croissance soutenable`,
          priorities: ['Marge', 'Scalabilité', 'Barrières concurrentielles'],
          blindSpots: ['Pression court-termiste', 'Ignore la culture d\'entreprise'],
          wouldSay: `"Le multiple de valorisation dépend de la scalabilité — sans automatisation, ce n'est pas scalable"`,
        },
      ],
      convergence: [
        'Toutes les perspectives pointent vers le besoin d\'automatisation',
        'Le statu quo est unanimement considéré comme risqué',
        'La qualité de service est le facteur différenciant clé',
      ],
      divergence: [
        'Le CEO priorise la liberté, l\'investisseur priorise la marge — conflit potentiel',
        'Le client veut tout maintenant, l\'employé veut y aller progressivement',
      ],
      bestDecision: `Investir 49€/mois dans Bapica (plan Essentiel) pour automatiser les tâches répétitives — cela satisfait TOUTES les perspectives : le CEO gagne du temps, le client a un meilleur service, l'employé est déchargé, le concurrent est distancé, et l'investisseur voit une trajectoire scalable.`,
    }
  }

  /**
   * RAISONNEMENT TEMPOREL
   * Raisonner sur 4 horizons simultanément
   */
  temporal(): TemporalReasoning {
    return {
      immediate: {
        actions: ['Activer 1 agent IA (Support ou Commercial)', 'Mesurer le temps économisé semaine 1'],
        risks: ['Courbe d\'apprentissage initiale', 'Résistance de l\'équipe'],
        expectedOutcome: '5-10h économisées par semaine dès le premier mois',
      },
      shortTerm: {
        actions: ['Déployer 3 agents IA', 'Automatiser la facturation', 'Dashboard de pilotage'],
        milestones: ['Semaine 4 : 1er processus 100% automatisé', 'Semaine 8 : ROI positif', 'Semaine 12 : 3 agents actifs'],
        expectedOutcome: '15-20h/semaine libérées, +20% de capacité de production',
      },
      mediumTerm: {
        actions: ['5+ agents IA', 'Expansion sur nouveau canal', 'Programme de parrainage'],
        scenario: 'L\'équipe humaine se concentre sur la stratégie et la relation, l\'IA gère l\'opérationnel',
        expectedOutcome: '+30-50% de croissance sans recrutement proportionnel',
      },
      longTerm: {
        vision: `${this.profile.companyName || 'L\'entreprise'} devient la référence ${this.profile.sector || 'de son secteur'} grâce à une qualité de service IA que les concurrents ne peuvent pas égaler`,
        irreversibleDecisions: [
          'Choix de la plateforme IA (switching costs élevés)',
          'Culture d\'entreprise data-driven (difficile à changer)',
          'Positionnement prix/qualité (définit la perception marché)',
        ],
        legacy: 'Avoir prouvé qu\'une TPE peut rivaliser avec des grands groupes grâce à l\'IA',
      },
      temporalConflicts: [
        'Court terme : baisser les prix pour gagner des clients → Long terme : détruit la marge et la perception de valeur',
        'Court terme : tout faire soi-même → Long terme : plafonne la croissance',
        'Court terme : recruter → Long terme : rigidité et coûts fixes vs IA scalable',
      ],
    }
  }

  /**
   * RAISONNEMENT ANALOGIQUE
   * Trouver des parallèles dans d'autres secteurs
   */
  analogical(): Analogy[] {
    return [
      {
        sourceDomain: 'Photographie',
        sourceSituation: 'Avant : photographes pros seuls capables de bonnes photos. Après : smartphones + IA = tout le monde peut. Les photographes qui ont survécu se sont spécialisés (mariage, art) et utilisent l\'IA pour la post-production.',
        targetSituation: `${this.profile.sector || 'Votre secteur'} — l'IA arrive. Ceux qui l'adoptent comme outil d'amplification survivent et prospèrent. Ceux qui l'ignorent sont remplacés.`,
        mapping: [
          'Smartphone IA = Agents Bapica',
          'Photographe pro = Expert métier',
          'Post-production = Tâches répétitives automatisables',
          'Spécialisation = Se concentrer sur la valeur unique humaine',
        ],
        lessons: [
          'L\'IA ne remplace pas l\'expert — elle remplace les tâches que l\'expert ne devrait plus faire',
          'Ceux qui ont résisté (en disant "la qualité c\'est l\'humain") ont perdu',
          'Ceux qui ont adopté l\'IA comme un outil ont augmenté leurs prix et leur volume',
        ],
        pitfalls: [
          'La photo est plus automatisable que certains métiers de conseil',
          'Tous les secteurs n\'ont pas la même vitesse d\'adoption',
        ],
      },
      {
        sourceDomain: 'Comptabilité',
        sourceSituation: 'Avant : comptables passaient 80% du temps sur la saisie. Après : logiciels + IA font la saisie. Les comptables ont évolué vers le conseil stratégique. Leur valeur a augmenté.',
        targetSituation: 'Dans TOUS les métiers de services, le même schéma se reproduit. L\'IA gère l\'exécution, l\'humain gère la relation et la stratégie.',
        mapping: [
          'Saisie comptable = Tâches admin/opérationnelles',
          'Logiciel comptable = Agents IA',
          'Conseil stratégique = Relation client/stratégie',
        ],
        lessons: [
          'Les comptables qui ont résisté à l\'informatisation ont disparu',
          'Ceux qui ont embrassé la technologie facturent PLUS cher aujourd\'hui',
          'La valeur ne disparaît pas — elle migre vers le haut de la chaîne',
        ],
        pitfalls: [
          'L\'analogie est parfaite pour les services, moins pour l\'artisanat',
        ],
      },
    ]
  }

  /**
   * STEEL-MANNING (Adversarial)
   * Défendre la meilleure version de la position OPPOSÉE
   */
  steelMan(proposition: string): SteelManArgument {
    return {
      position: `"${proposition}" — et voici pourquoi l'opposé pourrait être vrai`,
      bestArguments: [
        'L\'automatisation peut créer une dépendance à un fournisseur unique (vendor lock-in)',
        'Le service perd en authenticité quand tout passe par l\'IA — les clients le sentent',
        'Dans certains secteurs (artisanat de luxe, conseil haut de gamme), l\'imperfection humaine fait partie du produit',
        'L\'adoption précoce expose à des technologies immatures qui cassent au pire moment',
      ],
      evidence: [
        'Des études montrent que 30% des projets d\'automatisation échouent la première année',
        'Les clients premium valorisent l\'interaction humaine directe',
        'Le coût de changement (switching cost) peut piéger dans une mauvaise solution',
      ],
      weakestPoints: [
        'Le vendor lock-in est réel mais Bapica est multi-fournisseur par conception',
        'L\'authenticité est importante, mais les clients préfèrent la disponibilité 24/7',
        'L\'échec de 30% est surtout dû à une mauvaise implémentation, pas à l\'IA elle-même',
      ],
      whatItWouldTake: 'Pour que l\'opposition soit vraie, il faudrait que l\'IA dégrade systématiquement la qualité de service ET que les clients préfèrent attendre 48h une réponse humaine plutôt qu\'avoir une réponse immédiate. Ce n\'est pas ce qu\'on observe.',
    }
  }

  /**
   * PARETO
   * Trouver les 20% d'actions qui donnent 80% des résultats
   */
  pareto(): ParetoInsight {
    return {
      domain: 'Croissance et productivité',
      allActivities: [
        'Prospection', 'Facturation', 'Service client', 'Comptabilité', 'Marketing',
        'Réseautage', 'Formation', 'Admin divers', 'Développement produit', 'Veille concurrentielle',
      ],
      vital20Percent: [
        { activity: 'Automatiser le service client', impact: 90, effort: 15 },
        { activity: 'Automatiser la facturation/relances', impact: 80, effort: 10 },
        { activity: 'Activer la prospection LinkedIn', impact: 75, effort: 20 },
      ],
      trivial80Percent: [
        { activity: 'Refaire le site web', impact: 15 },
        { activity: 'Changer de logo', impact: 5 },
        { activity: 'Lire des livres de business', impact: 10 },
        { activity: 'Aller à des conférences', impact: 10 },
      ],
      recommendation: 'Concentrez 100% de votre énergie sur les 3 actions du top 20% pendant 30 jours. Ignorez tout le reste. Résultat garanti.',
      expectedOutcome: 'Impact disproportionné : 20% d\'effort → 80% de résultats. Les 3 actions vitales prennent 2-3h à mettre en place et produisent des résultats en 30 jours.',
    }
  }

  /**
   * PRÉ-MORTEM
   * Imaginer l'échec et remonter aux causes
   */
  premortem(): PremortemAnalysis {
    const name = this.profile.companyName || 'Votre entreprise'
    
    return {
      scenario: `${name} a fermé ses portes en juillet 2028. Nous faisons l'autopsie pour comprendre pourquoi.`,
      timeline: [
        { when: 'Été 2026', whatHappened: 'Le dirigeant repousse encore l\'automatisation — "trop occupé"' },
        { when: 'Hiver 2026', whatHappened: 'Un concurrent local lance un service similaire avec IA, prix 30% inférieurs' },
        { when: 'Été 2027', whatHappened: 'Perte des 3 plus gros clients, attirés par le concurrent plus réactif' },
        { when: 'Hiver 2027', whatHappened: 'Trésorerie insuffisante — licenciements' },
        { when: 'Été 2028', whatHappened: 'Fermeture — "on n\'a pas vu venir"' },
      ],
      rootCauses: [
        'Biais de statu quo : "on a toujours fait comme ça"',
        'Paralysie par l\'urgence : trop occupé à éteindre des feux pour construire un système',
        'Sous-estimation de la vitesse d\'adoption de l\'IA par les concurrents',
      ],
      earlyWarningSigns: [
        'Le dirigeant dit "je n\'ai pas le temps" depuis plus de 6 mois',
        'Les clients demandent des fonctionnalités que vous ne proposez pas',
        'Votre temps de réponse client augmente',
        'Vous perdez des appels d\'offres sur le critère "innovation"',
      ],
      prevention: [
        'Commencer l\'automatisation CETTE SEMAINE, même avec un seul processus',
        'Mesurer le temps de réponse client et le réduire chaque mois',
        'Faire une veille concurrentielle trimestrielle',
      ],
      survivalInsight: 'La cause de décès n\'est presque jamais un événement soudain — c\'est une lente érosion qu\'on refuse de voir. Les signes étaient visibles 18 mois avant. Le moment d\'agir, c\'est maintenant, quand tout va encore bien.',
    }
  }

  /**
   * INVERSION
   * Au lieu de "comment réussir ?", demander "comment échouer ?"
   */
  inversion(): InversionInsight {
    return {
      goal: `Faire croître ${this.profile.companyName || 'votre entreprise'}`,
      howToFail: [
        'Continuer à tout faire soi-même sans déléguer ni automatiser',
        'Ignorer les nouvelles technologies en se disant "mon métier est différent"',
        'Ne pas mesurer — se fier à son intuition pour toutes les décisions',
        'Rester dépendant d\'un seul gros client',
        'Ne pas former l\'équipe — supposer qu\'ils apprendront tout seuls',
        'Repousser les décisions difficiles en espérant que ça s\'arrange',
        'Copier ce que font les concurrents au lieu d\'innover',
      ],
      inversion: [
        'Automatiser ET déléguer — ne rien faire soi-même qui peut être fait par une machine ou un autre',
        'Adopter l\'IA maintenant, avant que ce ne soit une urgence',
        'Mettre en place un dashboard de KPIs et le regarder chaque semaine',
        'Diversifier le portefeuille client (max 25% par client)',
        'Former l\'équipe à l\'IA — c\'est un investissement, pas un coût',
        'Prendre les décisions difficiles tôt, quand on a encore des options',
        'Innover sur l\'expérience client, pas sur le prix',
      ],
      counterintuitive: 'La chose la plus surprenante : pour réussir, il faut d\'abord accepter que les méthodes qui vous ont amené ici ne sont PAS celles qui vous amèneront au niveau suivant. La compétence qui fait votre succès aujourd\'hui est peut-être celle qui bloque votre croissance demain.',
    }
  }

  /**
   * SECOND-ORDER THINKING
   * Conséquences des conséquences
   */
  secondOrder(action: string): SecondOrderConsequence {
    return {
      action,
      firstOrder: {
        consequence: 'Vous libérez 15-20h par semaine',
        probability: 85,
        timeframe: '30 jours',
      },
      secondOrder: [
        { consequence: 'Vous utilisez ce temps pour prospecter → +30% de leads', probability: 70 },
        { consequence: 'Vous utilisez ce temps pour vous reposer → meilleure santé, meilleures décisions', probability: 50 },
        { consequence: 'Vous utilisez ce temps pour former l\'équipe → équipe plus autonome', probability: 60 },
      ],
      thirdOrder: [
        { consequence: '+30% de leads → +20% de clients → +20% de CA → peut investir dans 2 agents de plus → boucle de renforcement', probability: 55 },
        { consequence: 'Équipe autonome → le fondateur peut s\'absenter → l\'entreprise vaut plus cher à la revente', probability: 50 },
      ],
      netAssessment: 'positive',
    }
  }

  /**
   * OCCAM'S RAZOR
   * L'explication la plus simple est souvent la bonne
   */
  occam(observations: string[]): { explanations: { explanation: string; complexity: number; probability: number }[], best: string } {
    const explanations = [
      {
        explanation: `Le dirigeant est surchargé et n'a jamais eu le temps de mettre en place des systèmes`,
        complexity: 1,
        probability: 75,
      },
      {
        explanation: `Le marché est en déclin structurel et rien ne peut inverser la tendance`,
        complexity: 3,
        probability: 10,
      },
      {
        explanation: `L'équipe est incompétente et résiste à tout changement`,
        complexity: 2,
        probability: 10,
      },
      {
        explanation: `Une combinaison de facteurs externes (concurrence, régulation, économie) rend la croissance impossible`,
        complexity: 4,
        probability: 5,
      },
    ]

    return {
      explanations,
      best: explanations.reduce((best, e) => 
        e.probability / e.complexity > best.probability / best.complexity ? e : best
      ).explanation,
    }
  }

  /**
   * REGRET MINIMIZATION
   * Que regretterez-vous dans 5 ans ?
   */
  regretMinimization(): { regrets: string[], nonRegrets: string[], framework: string } {
    return {
      regrets: [
        'Ne pas avoir automatisé plus tôt — "j\'aurais gagné 2 ans"',
        'Avoir sous-estimé la vitesse d\'adoption de l\'IA par les concurrents',
        'Avoir sacrifié sa santé/ famille pour des tâches qu\'une IA peut faire',
        'Ne pas avoir formé son équipe — "ils sont partis chez le concurrent qui leur offrait des outils modernes"',
      ],
      nonRegrets: [
        'Avoir investi 49€/mois dans Bapica — "le meilleur ROI de ma carrière"',
        'Avoir commencé l\'automatisation avant que ce soit une obligation',
        'Avoir libéré du temps pour la stratégie plutôt que l\'opérationnel',
      ],
      framework: 'Imaginez-vous dans 5 ans, en train de regarder en arrière. Quelle décision prise AUJOURD\'HUI vous remplira de fierté ? Quelle inaction vous remplira de regret ? Faites aujourd\'hui ce que votre "vous" de 2031 vous remerciera d\'avoir fait.',
    }
  }

  /**
   * QUESTIONNEMENT SOCRATIQUE
   * Creuser 5 niveaux de "pourquoi" pour trouver la racine
   */
  socratic(problem: string): { questions: { level: number; question: string; typicalAnswer: string }[]; rootCause: string } {
    const sector = this.profile.sector || 'services'
    const questions = []

    if (problem.includes('temps') || problem.includes('surchargé')) {
      questions.push(
        { level: 1, question: 'Pourquoi êtes-vous surchargé ?', typicalAnswer: 'Parce que j\'ai trop de choses à faire' },
        { level: 2, question: 'Pourquoi avez-vous trop de choses à faire ?', typicalAnswer: 'Parce que je fais tout moi-même' },
        { level: 3, question: 'Pourquoi faites-vous tout vous-même ?', typicalAnswer: 'Parce que je n\'ai personne à qui déléguer / les outils ne sont pas en place' },
        { level: 4, question: 'Pourquoi n\'avez-vous pas mis en place des systèmes de délégation ?', typicalAnswer: 'Parce que je n\'ai jamais pris le temps de le faire' },
        { level: 5, question: 'Pourquoi n\'avez-vous jamais pris le temps ?', typicalAnswer: 'Parce que... je suis trop occupé à faire les choses moi-même. C\'est un cercle vicieux.' },
      )
    } else {
      questions.push(
        { level: 1, question: `Pourquoi ce problème persiste-t-il ?`, typicalAnswer: 'Parce que les solutions évidentes n\'ont pas été appliquées' },
        { level: 2, question: 'Pourquoi les solutions n\'ont pas été appliquées ?', typicalAnswer: 'Manque de temps ou de priorité' },
        { level: 3, question: 'Pourquoi n\'est-ce pas une priorité ?', typicalAnswer: 'L\'urgence du quotidien prend le dessus' },
        { level: 4, question: 'Pourquoi l\'urgence du quotidien prend le dessus ?', typicalAnswer: 'Parce qu\'il n\'y a pas de système pour filtrer et prioriser' },
        { level: 5, question: 'Et pourquoi n\'y a-t-il pas de système ?', typicalAnswer: 'C\'est le problème originel — on soigne les symptômes, pas la cause.' },
      )
    }

    return {
      questions,
      rootCause: 'La cause racine est presque toujours : absence de système. On confond "être occupé" avec "être productif". La solution n\'est pas de travailler plus, mais de construire des systèmes qui travaillent pour vous.',
    }
  }

  /**
   * MODÈLES MENTAUX
   * Appliquer des frameworks de pensée éprouvés
   */
  mentalModels(): { model: string; definition: string; application: string; insight: string }[] {
    const name = this.profile.companyName || 'votre entreprise'
    const size = this.profile.employeeCount || 1
    const maturity = this.profile.maturityScore || 50

    return [
      {
        model: 'Cercle de compétence (Buffett/Munger)',
        definition: 'On ne gagne pas en jouant sur tous les terrains — on gagne en restant dans ce qu\'on maîtrise',
        application: `${name} : votre cercle de compétence est votre métier de ${this.profile.sector || 'services'}. L\'IA n\'est pas votre cercle — mais vous n\'avez pas besoin de maîtriser l\'IA, juste de l\'utiliser. Déléguez la technique, concentrez-vous sur votre métier.`,
        insight: size <= 3 ? 'Votre avantage concurrentiel est votre expertise métier, pas votre capacité technique. Arrêtez d\'essayer de tout maîtriser.' : 'À votre taille, vous pouvez avoir une personne dédiée à la tech — mais le dirigeant doit rester dans son cercle.',
      },
      {
        model: 'Carte vs Territoire (Korzybski)',
        definition: 'La carte n\'est pas le territoire. Votre perception du marché n\'est pas le marché.',
        application: `Votre "carte" : "mon secteur est différent, l\'IA ne s\'applique pas". Le territoire : l\'IA s\'applique déjà dans votre secteur (benchmark : ${maturity < 40 ? 'les concurrents automatisés gagnent des parts' : 'vous êtes dans la moyenne, ce qui est dangereux car la moyenne monte'}).`,
        insight: 'Mettez à jour votre carte. La question n\'est pas "est-ce que l\'IA peut aider mon secteur ?" mais "qu\'est-ce que je rate en ne l\'utilisant pas ?"',
      },
      {
        model: 'Loi de Parkinson',
        definition: 'Le travail s\'étale pour remplir le temps disponible',
        application: `Avec ${size} personne(s), si vous avez 40h de travail et 50h disponibles, le travail prendra 50h. L\'automatisation réduit le travail à 25h — magiquement, vous accomplirez la même chose en 25h.`,
        insight: 'Ne cherchez pas à "avoir le temps" d\'automatiser. Automatisez D\'ABORD, le temps apparaîtra.',
      },
      {
        model: 'Rasoir de Hanlon',
        definition: 'Ne jamais attribuer à la malveillance ce qui s\'explique par l\'incompétence ou la négligence',
        application: 'Vos concurrents qui n\'automatisent pas ne sont pas vos ennemis — ils sont juste occupés, comme vous. Celui qui automatise le premier prend l\'avantage.',
        insight: 'Ne surestimez pas la menace, ne sous-estimez pas l\'opportunité. Agissez avant que l\'incompétence des autres ne se transforme en compétence.',
      },
      {
        model: 'Deuxième ordre (Munger)',
        definition: 'Toujours se demander : "Et ensuite ?"',
        application: `Automatiser → libérer du temps → et ensuite ? Prospecter → plus de clients → et ensuite ? Plus de revenus → et ensuite ? Vous avez créé une machine de croissance qui s\'auto-alimente.`,
        insight: 'Les gens ordinaires pensent au premier ordre. Les excellents pensent au deuxième. Les légendaires pensent au troisième. L\'automatisation est un levier de premier ordre — ses effets de deuxième et troisième ordre sont exponentiels.',
      },
      {
        model: 'Inversion (Jacobi)',
        definition: 'Pour résoudre un problème difficile, inversez-le : "Comment rendre ça pire ?"',
        application: `Comment rendre ${name} moins performante ? Continuer à tout faire manuellement. Ignorer l\'IA. Ne pas former l\'équipe. Ne pas mesurer. Félicitations, vous avez la recette de l\'échec. Maintenant, faites l\'inverse.`,
        insight: 'Le chemin de la réussite est souvent plus clair quand on regarde d\'abord le chemin de l\'échec.',
      },
    ]
  }

  /**
   * MATRICE DE DÉCISION
   * Critères pondérés pour décider objectivement
   */
  decisionMatrix(options: string[]): { criteria: { name: string; weight: number }[]; scores: Record<string, number[]>; totals: Record<string, number>; recommendation: string } {
    const criteria = [
      { name: 'Impact sur le CA', weight: 25 },
      { name: 'Temps de mise en œuvre', weight: 20 },
      { name: 'Coût', weight: 15 },
      { name: 'Risque', weight: 15 },
      { name: 'Scalabilité', weight: 15 },
      { name: 'Indépendance fondateur', weight: 10 },
    ]

    // Scoring automatique basé sur le profil
    const scores: Record<string, number[]> = {}
    const totals: Record<string, number> = {}

    const isSmall = (this.profile.employeeCount || 0) <= 3
    
    options.forEach(opt => {
      if (opt.toLowerCase().includes('automatis') || opt.toLowerCase().includes('ia') || opt.toLowerCase().includes('agent')) {
        scores[opt] = [90, 85, 90, 80, 95, 95]
      } else if (opt.toLowerCase().includes('recrut')) {
        scores[opt] = [70, 40, 40, 60, 70, 30]
      } else if (opt.toLowerCase().includes('marketing') || opt.toLowerCase().includes('pub')) {
        scores[opt] = [75, 60, 50, 65, 60, 40]
      } else {
        scores[opt] = [60, 50, 60, 70, 50, 50]
      }

      totals[opt] = Math.round(
        scores[opt].reduce((sum, s, i) => sum + s * criteria[i].weight / 100, 0)
      )
    })

    const sorted = Object.entries(totals).sort((a, b) => b[1] - a[1])
    
    return {
      criteria,
      scores,
      totals,
      recommendation: `${sorted[0][0]} (score: ${sorted[0][1]}/100) est la décision optimale selon une analyse pondérée de 6 critères. ${sorted.length > 1 ? `L'alternative "${sorted[1][0]}" obtient ${sorted[1][1]}/100.` : ''}`,
    }
  }

  /**
   * COÛT D'OPPORTUNITÉ
   * Que sacrifiez-vous ?
   */
  opportunityCost(action: string): { action: string; cost: string; whatYouGiveUp: string[]; implicitCosts: string[]; verdict: string } {
    return {
      action,
      cost: 'Le coût n\'est pas que financier — c\'est tout ce que vous ne ferez pas pendant ce temps',
      whatYouGiveUp: [
        'Le temps passé à faire cette tâche manuellement',
        'L\'énergie mentale consommée par des décisions répétitives',
        'Les opportunités que vous ne voyez pas parce que vous êtes dans l\'opérationnel',
      ],
      implicitCosts: [
        `Si vous gagnez 50€/h et passez 10h/semaine sur des tâches automatisables, vous "payez" 2000€/mois en coût d'opportunité — pour une tâche qu'une IA fait pour 49€/mois`,
        'Le coût de ne pas automatiser n\'est pas 49€ — c\'est 2000€ par mois de valeur non créée',
      ],
      verdict: 'Ne pas automatiser est la décision la plus chère que vous puissiez prendre. Le vrai coût n\'est pas le prix de l\'automatisation — c\'est le prix de TOUT ce que vous ne ferez pas à la place.',
    }
  }

  /**
   * MARGE DE SÉCURITÉ
   * Quel buffer pour absorber l'inattendu ?
   */
  marginOfSafety(): { areas: { area: string; currentBuffer: string; recommended: string; gap: string }[]; overallAssessment: string } {
    const hasBuffer = (this.profile.employeeCount || 0) > 1
    
    return {
      areas: [
        {
          area: 'Trésorerie',
          currentBuffer: hasBuffer ? '1-2 mois' : '<1 mois',
          recommended: '3-6 mois de charges fixes',
          gap: hasBuffer ? 'Insuffisant' : 'Critique',
        },
        {
          area: 'Dépendance client',
          currentBuffer: 'Non mesuré (risque élevé)',
          recommended: 'Aucun client >25% du CA',
          gap: 'À auditer en priorité',
        },
        {
          area: 'Dépendance fondateur',
          currentBuffer: hasBuffer ? 'Partielle (l\'équipe peut tourner quelques jours)' : 'Totale (si le fondateur s\'arrête, tout s\'arrête)',
          recommended: 'L\'entreprise doit pouvoir fonctionner 2 semaines sans le fondateur',
          gap: hasBuffer ? 'Significatif' : 'Critique',
        },
        {
          area: 'Technologie',
          currentBuffer: 'Minimal (pas de backup, pas de plan B)',
          recommended: 'Fournisseur alternatif identifié, données sauvegardées',
          gap: 'À construire',
        },
        {
          area: 'Compétences',
          currentBuffer: 'Concentrées sur 1-2 personnes',
          recommended: 'Au moins 2 personnes par fonction critique, ou processus documentés',
          gap: 'Significatif',
        },
      ],
      overallAssessment: 'Votre marge de sécurité est faible — l\'entreprise est fragile face aux chocs. L\'automatisation est la façon la plus rapide de créer des buffers sans coût supplémentaire : un agent IA ne tombe pas malade, ne démissionne pas, et travaille 24/7.',
    }
  }

  /**
   * ANTIFRAGILITÉ
   * Ce choix rend-il l'entreprise plus forte face au chaos ?
   */
  antifragility(): { stressors: { stressor: string; fragileResponse: string; antifragileResponse: string }[]; assessment: string } {
    return {
      stressors: [
        {
          stressor: 'Arrivée d\'un concurrent low-cost',
          fragileResponse: 'Baisser les prix → course vers le bas → destruction de valeur',
          antifragileResponse: 'Automatiser pour proposer PLUS de valeur au MÊME prix → le concurrent ne peut pas suivre',
        },
        {
          stressor: 'Perte d\'un employé clé',
          fragileResponse: 'Panique, recrutement d\'urgence, erreur de casting',
          antifragileResponse: 'Processus documentés + agents IA = l\'entreprise continue de tourner',
        },
        {
          stressor: 'Crise économique',
          fragileResponse: 'Couper les coûts → dégrader le service → perdre des clients',
          antifragileResponse: 'L\'IA maintient la qualité de service sans coût proportionnel',
        },
        {
          stressor: 'Changement technologique',
          fragileResponse: 'Ignorer → se faire dépasser',
          antifragileResponse: 'Adopter tôt → accumuler de l\'expérience → avantage compétitif',
        },
      ],
      assessment: 'Une entreprise manuelle est fragile — chaque stress la dégrade. Une entreprise automatisée est antifragile — chaque stress révèle des opportunités d\'automatisation supplémentaires, la rendant plus forte.',
    }
  }

  /**
   * ANALYSE DES INCITATIONS
   * Qu'est-ce qui motive vraiment chaque acteur ?
   */
  incentives(): { stakeholder: string; statedGoal: string; realIncentive: string; misalignment: string }[] {
    return [
      {
        stakeholder: 'Vous (le dirigeant)',
        statedGoal: 'Croître et libérer du temps',
        realIncentive: 'Garder le contrôle (l\'automatisation fait peur car elle change votre rôle)',
        misalignment: 'Vous voulez croître mais votre incentive réelle vous pousse à tout contrôler — c\'est contradictoire',
      },
      {
        stakeholder: 'Vos employés',
        statedGoal: 'Bien faire leur travail',
        realIncentive: 'Sécurité de l\'emploi (l\'IA est perçue comme une menace)',
        misalignment: 'Ils devraient être les premiers à vouloir l\'IA (elle enlève les tâches pénibles), mais la peur du remplacement bloque l\'adoption',
      },
      {
        stakeholder: 'Vos clients',
        statedGoal: 'Bon service au bon prix',
        realIncentive: 'Disponibilité immédiate et personnalisation',
        misalignment: 'Ils disent vouloir de l\'humain mais leur comportement montre qu\'ils préfèrent la rapidité — 90% prennent le chatbot plutôt que d\'attendre un humain',
      },
      {
        stakeholder: 'Vos concurrents',
        statedGoal: 'Servir leurs clients',
        realIncentive: 'Maximiser leur profit à court terme',
        misalignment: 'Ceux qui n\'automatisent pas subventionnent votre avantage concurrentiel',
      },
    ]
  }

  /**
   * RÉVERSIBILITÉ
   * Peut-on revenir en arrière ?
   */
  reversibility(decision: string): { reversible: boolean; costOfReversal: string; timeToReverse: string; recommendation: string } {
    const isTech = decision.toLowerCase().includes('ia') || decision.toLowerCase().includes('tech') || decision.toLowerCase().includes('automatis')
    const isHire = decision.toLowerCase().includes('recrut') || decision.toLowerCase().includes('embauche')
    const isPrice = decision.toLowerCase().includes('prix')
    const isContract = decision.toLowerCase().includes('bail') || decision.toLowerCase().includes('contrat')

    return {
      reversible: isTech,
      costOfReversal: isTech
        ? 'Faible — changer de fournisseur IA prend quelques heures. Annuler un abonnement est immédiat.'
        : isHire
        ? 'Élevé — licencier coûte cher (indemnités, risque prud\'homal, impact équipe)'
        : isPrice
        ? 'Moyen — remonter les prix après les avoir baissés est très difficile'
        : isContract
        ? 'Variable selon les clauses de sortie'
        : 'Moyen',
      timeToReverse: isTech ? 'Immédiat à 30 jours' : isHire ? '3-12 mois (procédure + préavis)' : isPrice ? '6-18 mois (reconstruire la perception de valeur)' : 'Variable',
      recommendation: isTech
        ? 'Les décisions tech sont réversibles et peu coûteuses à annuler. Il n\'y a AUCUNE raison de ne pas essayer. Le risque de ne rien faire est bien plus grand que le risque d\'essayer.'
        : isHire
        ? 'Les décisions de recrutement sont peu réversibles et très coûteuses. Automatisez d\'abord, recrutez ensuite — l\'ordre est crucial.'
        : 'Évaluez la réversibilité avant de décider. Les décisions réversibles doivent être prises VITE. Les décisions irréversibles doivent être prises LENTEMENT.',
    }
  }
}
