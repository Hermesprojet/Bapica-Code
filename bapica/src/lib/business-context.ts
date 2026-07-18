import { analyzeBusinessProfile } from '@/lib/business-profile'

// Construit un BRIEF business du client à injecter dans le prompt de CHAQUE
// agent, pour qu'ils « maîtrisent » l'entreprise du client et conseillent
// concrètement (pas de généralités). Reste compact pour ne pas noyer le prompt.
//
// `onboarding` = le contenu de user_metadata.onboarding_data (voir onboarding).
export function buildBusinessBrief(onboarding: any): string {
  if (!onboarding || typeof onboarding !== 'object' || Object.keys(onboarding).length === 0) {
    return ''
  }

  const o = onboarding
  const facts: string[] = []

  const company = (o.companyName || '').trim()
  if (company) facts.push(`Entreprise : ${company}`)
  const activity = o.activityOther?.trim() || o.activity
  if (activity) facts.push(`Type : ${activity}`)
  if (o.website) facts.push(`Site : ${o.website}`)
  if (o.city || o.country) facts.push(`Localisation : ${[o.city, o.country].filter(Boolean).join(', ')}`)
  if (o.revenue) facts.push(`Chiffre d'affaires : ${o.revenue}`)
  if (o.businessDescription) facts.push(`Activité décrite par le client : ${String(o.businessDescription).slice(0, 400)}`)
  if (o.mainProblem) facts.push(`Défi principal : ${String(o.mainProblem).slice(0, 300)}`)
  if (o.growthGoal) facts.push(`Objectif prioritaire : ${o.growthGoal}`)
  if (Array.isArray(o.objectives) && o.objectives.length) facts.push(`Objectifs : ${o.objectives.join(', ')}`)
  if (Array.isArray(o.adminTasks) && o.adminTasks.length) facts.push(`Tâches chronophages : ${o.adminTasks.join(', ')}`)
  if (Array.isArray(o.contactMethods) && o.contactMethods.length) facts.push(`Canaux clients : ${o.contactMethods.join(', ')}`)
  const apps = Array.isArray(o.apps) ? o.apps.map((a: any) => (typeof a === 'string' ? a : a?.name)).filter(Boolean) : []
  if (apps.length) facts.push(`Outils utilisés : ${apps.join(', ')}`)

  // Analyse dérivée (résumé + opportunités + points de vigilance)
  let derived = ''
  try {
    const bp = analyzeBusinessProfile(o)
    const bits: string[] = []
    if (bp.profileSummary) bits.push(bp.profileSummary)
    if (bp.growthOpportunities?.length) bits.push('Leviers de croissance : ' + bp.growthOpportunities.slice(0, 3).join(' ; '))
    if (bp.riskFactors?.length) {
      const risks = bp.riskFactors.slice(0, 2).map((r: any) => (typeof r === 'string' ? r : r?.risk)).filter(Boolean)
      if (risks.length) bits.push('Points de vigilance : ' + risks.join(' ; '))
    }
    derived = bits.join('\n')
  } catch { /* analyse optionnelle */ }

  if (facts.length === 0 && !derived) return ''

  return [
    "PROFIL DE L'ENTREPRISE DU CLIENT (utilise-le pour conseiller concrètement, jamais en le récitant, jamais « d'après ton profil ») :",
    ...facts,
    derived,
    "Appuie chaque conseil sur ce contexte réel (secteur, taille, défi, objectif, outils). Ne redemande pas une info déjà présente ici.",
  ].filter(Boolean).join('\n')
}
