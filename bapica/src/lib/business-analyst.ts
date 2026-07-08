/**
 * Business Analyst IA conversationnel + Contexte sectoriel enrichi
 */
import Anthropic from '@anthropic-ai/sdk'

// ============================================================
// CONTEXTE SECTORIEL ENRICHI
// ============================================================

function getSectorContext(profile: any): string {
  const sector = profile.sector || 'services'
  const size = profile.companySize || 'TPE'
  const stage = profile.stage || 'early'
  const employees = profile.employeeCount || 1
  
  const contexts: Record<string, string> = {
    ecommerce: `CONTEXTE E-COMMERCE :
Enjeux : taux de conversion (2-3%), panier moyen, abandon panier (70%), fidélisation. Canaux : SEO produit, ads, email, marketplace. Risques : dépendance canal, rupture stock, saisonnalité. Opportunités IA : fiches produits SEO, support 24/7, relance panier, analyse avis. Pour ${employees} personne(s) : automatiser contenu et support = levier n°1.`,

    services: `CONTEXTE SERVICES & CONSEIL :
Enjeux : conversion devis (20-40%), LTV, taux horaire facturable, référencement. Canaux : recommandation, LinkedIn, site vitrine. Risques : dépendance fondateur, irrégularité revenus, impayés. Opportunités IA : prospection LinkedIn, relance devis, rédaction propositions, facturation auto, contenu expert. Pour ${employees} personne(s) : prospection + admin tuent la rentabilité. Stade ${stage} : ${stage === 'early' ? 'priorité ABSOLUE prospection' : stage === 'growth' ? 'structurer processus avant recruter' : 'automatiser pour scaler'}.`,

    sante: `CONTEXTE SANTÉ & BIEN-ÊTRE :
Enjeux : remplissage agenda, no-show patients (20-30%), fidélisation, RGPD données santé. Canaux : téléphone (80% RDV), Doctolib, recommandation. Risques : RDV non honorés, admin lourd, réglementation. Opportunités IA : standard téléphonique 24/7, relance SMS pré-RDV, gestion prescriptions, FAQ patients, compta. Pour ${employees} personne(s) : téléphone = outil n°1, automatiser libère 15-20h/semaine.`,

    formation: `CONTEXTE FORMATION & COACHING :
Enjeux : remplissage sessions, coût acquisition élève, complétion, Qualiopi. Canaux : contenu (SEO, blog, YouTube), LinkedIn, partenariats. Risques : saisonnalité inscriptions, concurrence plateformes, pédagogie chronophage. Opportunités IA : contenu pédagogique (modules, quiz), posts LinkedIn, automatisation inscriptions, supports de cours, suivi élèves. Pour ${employees} personne(s) : le contenu = votre produit, IA multiplie production par 5.`,

    immobilier: `CONTEXTE IMMOBILIER :
Enjeux : mandats, conversion visites→ventes, délai vente. Canaux : téléphone (1 appel manqué = 1 mandat perdu), portails, recommandation. Risques : appels manqués (50%+), admin lourd, saisonnalité. Opportunités IA : agent téléphonique 24/7, suivi prospects auto, contenu annonces, relance contacts, docs admin.`,

    btp: `CONTEXTE BTP & ARTISANAT :
Enjeux : conversion devis (10-30%), marge chantier, délais paiement. Canaux : téléphone (urgences), recommandation, Google Maps. Risques : appels manqués = chantiers perdus, devis chronophages, impayés. Opportunités IA : réception appels 24/7, devis types, relance factures, suivi chantier, réponse avis Google.`,

    saas: `CONTEXTE SAAS & TECH :
Enjeux : MRR growth (10-20%/mois), churn (<5%), CAC payback, NPS. Canaux : content marketing, Product Hunt, outbound. Risques : churn, product-market fit, concurrence US. Opportunités IA : content marketing auto, support technique IA, analyse churn, prospection outbound, génération code/doc.`,

    commerce: `CONTEXTE COMMERCE LOCAL :
Enjeux : panier moyen, fréquence visite, rétention, visibilité locale. Canaux : Google My Business, réseaux sociaux, vitrine, SMS/WhatsApp. Risques : dépendance passage physique, concurrence e-commerce, saisonnalité. Opportunités IA : contenu local, réponse avis Google auto, campagnes SMS, gestion stocks, fidélisation.`,

    freelance: `CONTEXTE FREELANCE :
Enjeux : taux journalier, pipeline missions, temps non facturable (30-40%). Risques : tout repose sur UNE personne, irrégularité revenus. Opportunités IA : prospection LinkedIn, facturation/relances auto, contenu portfolio, assistant admin, recherche missions. Pour ${employees} personne : admin qui tue productivité = priorité n°1.`,

    logistique: `CONTEXTE LOGISTIQUE & TRANSPORT :
Enjeux : taux remplissage, coût/km, délais, SLA. Canaux : téléphone urgences, email, plateformes. Risques : appels urgents 24/7, optimisation tournées, prix carburant. Opportunités IA : appels urgents auto, suivi colis, optimisation tournées, relation client proactive, analyse coûts.`,

    finance: `CONTEXTE FINANCE & ASSURANCE :
Enjeux : CAC élevé, LTV, conformité (ACPR/AMF), taux closing. Risques : conformité lourde, cycle vente long, concurrence assurtechs. Opportunités IA : analyse portefeuille, rapports financiers, conformité documentaire, prospection B2B, support client.`,

    restauration: `CONTEXTE RESTAURATION :
Enjeux : taux remplissage, panier moyen, note Google (crucial), gestion stocks. Canaux : téléphone (60%+ CA), Google Maps, Instagram, TheFork. Risques : appels pendant service, avis négatifs, stocks. Opportunités IA : réservation téléphonique 24/7, réponse avis auto, contenu Instagram, menus personnalisés.`,
  }

  return contexts[sector] || contexts.services
}

// ============================================================
// ANALYSE CONVERSATIONNELLE
// ============================================================

export async function analyzeUserQuery(
  query: string,
  profile: any,
  chatHistory: Array<{role: string, content: string}> = []
): Promise<string> {
  const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY || '' })

  const systemPrompt = `Tu es l'analyste business IA de Bapica. Tu as accès au profil complet de l'entreprise ET à des données sectorielles précises.

Tu es :
- Direct et pragmatique (pas de blabla)
- Concret (des chiffres, des actions, pas de théorie)
- Challengeant (tu dis ce qui ne va pas)
- Ultra-contextuel (tu utilises les données du profil ET le contexte sectoriel)

Tu réponds en 4-8 phrases. Tu cites des chiffres spécifiques au secteur.
Tu mentionnes toujours le nom du secteur dans ta réponse.`

  const contextPrompt = `Profil complet :

🏢 ${profile.companyName || 'Entreprise'}
📊 Secteur : ${profile.sector || 'Non spécifié'}
👥 Taille : ${profile.companySize || 'TPE'} — ${profile.employeeCount || 1} pers
📈 Stade : ${profile.stage || 'early'}
🎯 Maturité digitale : ${profile.maturityScore || 'N/A'}/100
📋 Priorités : ${(profile.priorities || []).join(', ') || 'Non définies'}
⚠️ Points de douleur : ${(profile.painPoints || []).join(', ') || 'Aucun'}
📣 Acquisition : ${(profile.customerAcquisition || []).join(', ') || 'N/A'}
🔧 Outils : ${(profile.currentTools || []).join(', ') || 'Aucun'}
🤖 Agents : ${(profile.recommendedAgents || []).join(', ')}

${getSectorContext(profile)}

Question : ${query}

Réponds en utilisant le contexte sectoriel ET le profil. Sois ultra-spécifique.`

  const messages: any[] = [
    ...chatHistory.slice(-6).map(m => ({ role: m.role, content: m.content })),
    { role: 'user', content: contextPrompt },
  ]

  const msg = await anthropic.messages.create({
    model: 'claude-haiku-4-5',
    max_tokens: 400,
    system: systemPrompt,
    temperature: 0.5,
    messages,
  })

  return (msg.content as any[]).find((b: any) => b.type === 'text')?.text || 'Analyse indisponible.'
}

// ============================================================
// INSIGHTS PROACTIFS
// ============================================================

export async function generateInsights(profile: any): Promise<string[]> {
  const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY || '' })

  const prompt = `Génère 3 insights ACTIONABLES pour cette entreprise :
🏢 ${profile.companyName} — Secteur : ${profile.sector}
👥 ${profile.employeeCount || 1} pers — stade ${profile.stage}
🎯 Maturité : ${profile.maturityScore}/100

${getSectorContext(profile)}

Format : UNIQUEMENT 3 phrases séparées par |. Chaque phrase doit mentionner le secteur.`

  const msg = await anthropic.messages.create({
    model: 'claude-haiku-4-5',
    max_tokens: 300,
    temperature: 0.7,
    messages: [{ role: 'user', content: prompt }],
  })

  const text = (msg.content as any[]).find((b: any) => b.type === 'text')?.text || ''
  return text.split('|').map((s: string) => s.trim()).filter(Boolean).slice(0, 3)
}
