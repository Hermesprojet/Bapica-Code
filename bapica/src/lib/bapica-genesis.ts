/**
 * Bapica Genesis — Auto-configuration, Pré-cognition, Hub Orchestration
 * 
 * Court terme / Impact immédiat :
 * 1. Auto-configuration — Zéro setup, Bapica s'auto-configure
 * 2. Pré-cognition — Anticipe les besoins 3 mois à l'avance
 * 3. Hub Orchestration — Connecte tous les outils, optimise les flux
 */

// ─── 1. AUTO-CONFIGURATION ─────────────────────────────────

export interface AutoConfig {
  activatedAgents: string[]
  suggestedIntegrations: string[]
  defaultAlerts: string[]
  onboardingComplete: boolean
  confidence: number
  reasoning: string
}

/**
 * Bapica observe le profil client et s'auto-configure.
 * Zéro questionnaire. Zéro paramétrage.
 * Le dirigeant arrive → Bapica est déjà prête.
 */
export function autoConfigure(profile: {
  sector?: string
  employees?: string
  revenue?: string
  website?: string
  country?: string
  tools?: string[]
}): AutoConfig {
  const activated: string[] = ['general']
  const integrations: string[] = []
  const alerts: string[] = []
  const reasons: string[] = []

  // Toujours activer le Conseiller Croissance
  activated.push('prospection-strategie')
  reasons.push('Agent croissance activé par défaut')

  // Détection secteur
  if (profile.sector?.match(/restaurant|restauration|hôtel|hotel/i)) {
    activated.push('support', 'telephone')
    integrations.push('google_places', 'whatsapp')
    alerts.push('Avis clients à surveiller quotidiennement')
    reasons.push('Secteur restauration → support + téléphone prioritaires')
  } else if (profile.sector?.match(/tech|saas|web|digital|logiciel/i)) {
    activated.push('trends', 'analytics')
    integrations.push('github', 'vercel', 'stripe')
    alerts.push('Veille concurrentielle hebdomadaire')
    reasons.push('Secteur tech → analytics + veille activés')
  } else if (profile.sector?.match(/btp|bâtiment|construction|artisan/i)) {
    activated.push('accounting', 'legal')
    integrations.push('pennylane', 'sage')
    alerts.push('Suivi de trésorerie recommandé (secteur à cycles longs)')
    reasons.push('BTP → compta + juridique prioritaires')
  } else if (profile.sector?.match(/commerce|retail|ecommerce/i)) {
    activated.push('analytics', 'support')
    integrations.push('shopify', 'woocommerce', 'stripe')
    alerts.push('Taux de conversion et panier moyen à suivre')
    reasons.push('Commerce → analytics + support activés')
  } else if (profile.sector?.match(/santé|medical|médical|cabinet/i)) {
    activated.push('legal', 'telephone')
    integrations.push('doctolib', 'google_places')
    alerts.push('⚠️ Conformité RGPD santé obligatoire')
    reasons.push('Santé → juridique + téléphone prioritaires')
  } else {
    activated.push('support', 'analytics')
    reasons.push('Configuration standard')
  }

  // Taille → modules
  const emp = parseInt(profile.employees || '1')
  if (emp >= 6) {
    activated.push('recruiter')
    reasons.push(`${emp} employés → module recrutement activé`)
  }
  if (emp >= 15) {
    integrations.push('hubspot', 'slack')
    reasons.push('Équipe > 15 → CRM + messagerie recommandés')
  }

  // CA → niveau de service
  const rev = profile.revenue || ''
  if (rev.includes('500K') || rev.includes('2M') || rev.includes('10M')) {
    activated.push('accounting', 'analytics')
    reasons.push('CA significatif → compta + analytics activés')
  }

  // Pays → conformité
  if (profile.country && profile.country !== 'France') {
    activated.push('legal')
    alerts.push(`⚠️ Conformité multi-pays (${profile.country}) à vérifier`)
    reasons.push(`Multi-pays → conformité activée`)
  }

  // Site web → audit
  if (profile.website) {
    alerts.push('Audit du site web recommandé')
  }

  return {
    activatedAgents: [...new Set(activated)],
    suggestedIntegrations: [...new Set(integrations)],
    defaultAlerts: alerts,
    onboardingComplete: true,
    confidence: Math.min(reasons.length * 10, 95),
    reasoning: reasons.join(' | '),
  }
}

// ─── 2. PRÉ-COGNITION ──────────────────────────────────────

export interface PreCognition {
  timeframe: '1mo' | '3mo' | '6mo' | '12mo'
  predictions: Prediction[]
  confidence: number
}

export interface Prediction {
  category: 'growth' | 'risk' | 'opportunity' | 'compliance' | 'resource'
  title: string
  description: string
  probability: number
  impact: 'low' | 'medium' | 'high'
  timeframe: string
  action: string
}

/**
 * Bapica anticipe l'avenir de la PME.
 * Toujours 3 mois d'avance sur les problèmes.
 */
export function predictFuture(profile: any, marketSignals: string[]): Prediction[] {
  const predictions: Prediction[] = []
  const id = (t: string) => `pred_${Date.now()}_${t}`

  // 1. Croissance → besoin recrutement
  const rev = profile.revenue || ''
  const emp = parseInt(profile.employees || '1')
  if (rev.includes('500K') && emp < 20) {
    predictions.push({
      category: 'resource',
      title: 'Goulot d\'étranglement humain imminent',
      description: `Avec ${emp} employés et un CA en croissance, chaque départ devient critique. Anticipez le recrutement d'au moins 2 personnes dans les 6 mois.`,
      probability: 0.78,
      impact: 'high',
      timeframe: '3-6 mois',
      action: 'Activer l\'agent Recrutement et préparer 2 fiches de poste',
    })
  }

  // 2. Trésorerie saisonnière
  if (profile.sector?.match(/commerce|retail|restaurant|btp/i)) {
    predictions.push({
      category: 'risk',
      title: 'Tension de trésorerie saisonnière',
      description: 'Votre secteur connaît des cycles saisonniers. Préparez une réserve de trésorerie pour la période creuse.',
      probability: 0.65,
      impact: 'high',
      timeframe: 'Selon saison',
      action: 'L\'agent Comptabilité peut vous aider à modéliser votre besoin de fonds de roulement',
    })
  }

  // 3. Conformité
  if (!profile.websiteHasLegalPages) {
    predictions.push({
      category: 'compliance',
      title: 'Risque juridique — absence de mentions légales',
      description: 'Votre site n\'a pas de mentions légales. Sanction possible jusqu\'à 75 000€ (RGPD) et 1 an d\'emprisonnement.',
      probability: 0.45,
      impact: 'high',
      timeframe: 'Immédiat',
      action: 'URGENT: L\'agent Juridique peut générer vos mentions légales en 5 minutes',
    })
  }

  // 4. Croissance → besoin CRM
  if (emp >= 8 && !profile.crm) {
    predictions.push({
      category: 'opportunity',
      title: 'Seuil de maturité — besoin CRM',
      description: 'À votre taille, un CRM augmente le CA de 29% en moyenne. Sans CRM, vous perdez des opportunités.',
      probability: 0.82,
      impact: 'high',
      timeframe: '1-3 mois',
      action: 'Évaluer HubSpot, Pipedrive ou Twenty CRM. L\'agent Croissance peut vous guider.',
    })
  }

  // 5. Intelligence collective
  if (marketSignals.length > 0) {
    predictions.push({
      category: 'opportunity',
      title: 'Signal marché détecté',
      description: marketSignals.join(' | '),
      probability: 0.55,
      impact: 'medium',
      timeframe: '3-6 mois',
      action: 'Surveiller ce signal. L\'agent Tendances peut approfondir.',
    })
  }

  // 6. Toujours : sécurité
  predictions.push({
    category: 'risk',
    title: 'Cyber-sécurité — risque permanent',
    description: '67% des PME ont subi une cyberattaque en 2025. Avez-vous des sauvegardes ? Un antivirus ? Des mots de passe forts ?',
    probability: 0.67,
    impact: 'high',
    timeframe: 'Permanent',
    action: 'Checklist cybersécurité disponible dans l\'agent Général',
  })

  return predictions.sort((a, b) => b.probability - a.probability)
}

// ─── 3. HUB ORCHESTRATION ──────────────────────────────────

export interface Workflow {
  id: string
  name: string
  trigger: string
  steps: WorkflowStep[]
  tools: string[]
  optimized: boolean
  timeSaved: string
}

export interface WorkflowStep {
  order: number
  tool: string
  action: string
  input: string
  output: string
  duration: string
  status: 'manual' | 'auto' | 'semi'
}

/**
 * Bapica comprend les flux entre outils et les optimise.
 * "J'ai détecté que votre workflow facture→paiement→compta a 3 jours de délai"
 */
export function detectWorkflows(connectedTools: string[]): Workflow[] {
  const workflows: Workflow[] = []

  // Workflow 1: Facture → Paiement → Compta
  if (connectedTools.includes('pennylane') || connectedTools.includes('stripe')) {
    workflows.push({
      id: 'invoice_to_accounting',
      name: 'Facture → Paiement → Comptabilité',
      trigger: 'Nouvelle facture créée',
      steps: [
        { order: 1, tool: 'Pennylane/Stripe', action: 'Créer facture', input: 'Données client', output: 'Facture PDF', duration: '5 min', status: 'auto' },
        { order: 2, tool: 'Gmail', action: 'Envoyer facture au client', input: 'Facture + email client', output: 'Email envoyé', duration: '1 min', status: 'auto' },
        { order: 3, tool: 'Gmail', action: 'Relance automatique J+7', input: 'Facture impayée', output: 'Email de relance', duration: '1 min', status: 'auto' },
        { order: 4, tool: 'Pennylane', action: 'Rapprochement bancaire', input: 'Paiement reçu', output: 'Écriture comptable', duration: '10 min', status: 'semi' },
      ],
      tools: ['pennylane', 'stripe', 'gmail'],
      optimized: true,
      timeSaved: '2h/mois',
    })
  }

  // Workflow 2: Lead → CRM → Relance
  if (connectedTools.includes('hubspot') || connectedTools.includes('twenty')) {
    workflows.push({
      id: 'lead_to_crm',
      name: 'Lead → Qualification → Relance',
      trigger: 'Nouveau lead détecté',
      steps: [
        { order: 1, tool: 'Bapica Croissance', action: 'Identifier lead', input: 'Formulaire/email', output: 'Lead qualifié', duration: '2 min', status: 'auto' },
        { order: 2, tool: 'CRM', action: 'Créer fiche contact', input: 'Données lead', output: 'Contact CRM', duration: '1 min', status: 'auto' },
        { order: 3, tool: 'Gmail', action: 'Email de prospection', input: 'Template + contact', output: 'Email envoyé', duration: '1 min', status: 'auto' },
        { order: 4, tool: 'Gmail', action: 'Relance J+3 si pas de réponse', input: 'Historique', output: 'Relance', duration: '1 min', status: 'auto' },
        { order: 5, tool: 'Calendar', action: 'Planifier RDV si réponse positive', input: 'Disponibilités', output: 'RDV confirmé', duration: '2 min', status: 'semi' },
      ],
      tools: ['hubspot', 'twenty', 'gmail', 'google_calendar'],
      optimized: true,
      timeSaved: '5h/mois',
    })
  }

  // Workflow 3: Support → Ticket → Résolution
  if (connectedTools.includes('zendesk') || connectedTools.includes('intercom')) {
    workflows.push({
      id: 'support_ticket',
      name: 'Ticket Support → Analyse → Résolution',
      trigger: 'Nouveau ticket client',
      steps: [
        { order: 1, tool: 'Support', action: 'Réception ticket', input: 'Message client', output: 'Ticket créé', duration: '0 min', status: 'auto' },
        { order: 2, tool: 'Bapica Support', action: 'Réponse automatique niveau 1', input: 'Base connaissance', output: 'Réponse suggérée', duration: '30 sec', status: 'auto' },
        { order: 3, tool: 'Bapica Support', action: 'Escalade si complexe', input: 'Ticket non résolu', output: 'Transfert humain', duration: '1 min', status: 'semi' },
        { order: 4, tool: 'Notion', action: 'Documenter la solution', input: 'Résolution', output: 'Fiche connaissance', duration: '5 min', status: 'auto' },
      ],
      tools: ['zendesk', 'intercom', 'notion'],
      optimized: true,
      timeSaved: '10h/mois',
    })
  }

  // Workflow 4: RH → Offre → Onboarding
  if (connectedTools.includes('payfit') || connectedTools.includes('bamboohr')) {
    workflows.push({
      id: 'recruit_to_onboarding',
      name: 'Recrutement → Contrat → Onboarding',
      trigger: 'Nouveau candidat retenu',
      steps: [
        { order: 1, tool: 'Bapica Recrutement', action: 'Générer fiche de poste', input: 'Description besoin', output: 'Fiche de poste', duration: '5 min', status: 'auto' },
        { order: 2, tool: 'Bapica Juridique', action: 'Générer contrat', input: 'Fiche de poste', output: 'Contrat PDF', duration: '5 min', status: 'auto' },
        { order: 3, tool: 'DocuSign', action: 'Signature électronique', input: 'Contrat', output: 'Contrat signé', duration: '1 jour', status: 'semi' },
        { order: 4, tool: 'RH', action: 'Créer fiche employé', input: 'Contrat signé', output: 'Employé dans le SIRH', duration: '10 min', status: 'auto' },
        { order: 5, tool: 'Notion', action: 'Créer parcours onboarding', input: 'Profil employé', output: 'Checklist onboarding', duration: '5 min', status: 'auto' },
      ],
      tools: ['payfit', 'bamboohr', 'docusign', 'notion'],
      optimized: true,
      timeSaved: '3h/recrutement',
    })
  }

  return workflows
}

/**
 * Score d'orchestration : à quel point la PME est automatisée
 */
export function orchestrationScore(workflows: Workflow[]): { score: number; message: string; potential: string } {
  const total = workflows.length
  const automated = workflows.filter(w => w.optimized).length
  const score = Math.round((automated / Math.max(total, 1)) * 100)

  return {
    score,
    message: score >= 70 ? '🎯 PME bien orchestrée' : score >= 40 ? '⚡ Orchestration partielle — optimisable' : '🔧 Peu orchestrée — fort potentiel d\'automatisation',
    potential: `${workflows.reduce((sum, w) => sum + parseInt(w.timeSaved), 0) || 0}h/mois économisables`,
  }
}
