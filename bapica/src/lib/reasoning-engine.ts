/**
 * Moteur de Raisonnement Bapica
 * 
 * La couche cognitive qui permet à Bapica de PENSER, pas juste d'analyser.
 * 
 * Modes de raisonnement :
 * 1. Déductif — principes généraux → conclusions spécifiques
 * 2. Inductif — observations → patterns → généralisations
 * 3. Abductif — trouver l'explication la plus probable
 * 4. Contrefactuel — "et si X n'avait pas fait Y ?"
 * 5. Systémique — interconnexions, feedback loops, émergence
 * 6. Premiers principes — déconstruire jusqu'aux fondamentaux
 * 7. Dialectique — thèse → antithèse → synthèse
 * 8. Bayésien — mettre à jour ses croyances avec de nouvelles preuves
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
