/**
 * Contexte sectoriel enrichi pour des réponses ultra-personnalisées
 */
function getSectorContext(profile: any): string {
  const sector = profile.sector || 'services'
  const size = profile.companySize || 'TPE'
  const stage = profile.stage || 'early'
  const employees = profile.employeeCount || 1
  
  const contexts: Record<string, string> = {
    ecommerce: `CONTEXTE SECTORIEL E-COMMERCE :
- Enjeux clés : taux de conversion (moy 2-3%), panier moyen, taux d'abandon panier (70%), fidélisation client
- Canaux critiques : SEO produit, ads (Meta/Google), email marketing, marketplace (Amazon, Cdiscount)
- Risques typiques : dépendance à un canal d'acquisition, rupture de stock, logistique, saisonnalité
- Opportunités IA : génération de fiches produits optimisées SEO, support client 24/7 (retours, SAV), emails de relance panier abandonné, analyse des avis clients
- Pour ${employees} personne(s) : automatiser la création de contenu et le support est le levier n°1
- Si maturité digitale ${profile.digitalMaturity || 'medium'} : ${profile.digitalMaturity === 'low' ? 'URGENT — automatiser les fiches produits et le SAV' : profile.digitalMaturity === 'high' ? 'optimiser les marges via analytics' : 'passer à l\'étape supérieure avec l\'IA'}`,

    services: `CONTEXTE SECTORIEL SERVICES & CONSEIL :
- Enjeux clés : taux de conversion devis (20-40%), valeur vie client (LTV), taux d'occupation/horaire facturable, référencement
- Canaux critiques : recommandation/bouche-à-oreille, LinkedIn, site vitrine, networking
- Risques typiques : dépendance au fondateur, irrégularité des revenus, périmètre flou, impayés
- Opportunités IA : prospection LinkedIn automatisée, relance devis, rédaction de propositions commerciales, facturation et relances automatiques, génération de contenu expert (articles, études de cas)
- Pour ${employees} personne(s) : la prospection et l'admin sont les 2 postes qui tuent la rentabilité
- Si stade ${profile.stage} : ${profile.stage === 'early' ? 'priorité ABSOLUE à la prospection pour sécuriser le pipeline' : profile.stage === 'growth' ? 'structurer les processus avant de recruter' : 'automatiser pour scaler sans perdre en qualité'}`,

    immobilier: `CONTEXTE SECTORIEL IMMOBILIER :
- Enjeux clés : nombre de mandats, taux de conversion visites→ventes, délai de vente, panier moyen
- Canaux critiques : téléphone (crucial — 1 appel manqué = 1 mandat perdu), portails (SeLoger, Leboncoin), recommandation
- Risques typiques : appels manqués (50%+ des prospects), administrative lourd, saisonnalité, concurrence locale
- Opportunités IA : agent téléphonique 24/7 (ne rate aucun appel), suivi automatique des prospects, création de contenus pour annonces, relance des anciens contacts, automatisation des documents administratifs`,

    sante: `CONTEXTE SECTORIEL SANTÉ & BIEN-ÊTRE :
- Enjeux clés : taux de remplissage agenda, no-show patients (20-30%), fidélisation, conformité RGPD données santé
- Canaux critiques : téléphone (80% des RDV), Doctolib/Maiia, recommandation, Google My Business
- Risques typiques : RDV non honorés, temps administratif excessif, rappels patients chronophages, réglementation stricte
- Opportunités IA : standard téléphonique IA pour prise de RDV 24/7, relance SMS/email automatique avant RDV, gestion des prescriptions et ordonnances, réponse aux questions patients fréquentes, comptabilité simplifiée
- Pour ${employees} personne(s) : le téléphone est votre 1er outil — l'automatiser libère 15-20h/semaine
- CRITIQUE : ne JAMAIS stocker de données médicales sans consentement explicite RGPD`,

    formation: `CONTEXTE SECTORIEL FORMATION & COACHING :
- Enjeux clés : taux de remplissage sessions, coût d'acquisition élève, taux de complétion, certification Qualiopi
- Canaux critiques : contenu (SEO, blog, YouTube), LinkedIn, partenariats, bouche-à-oreille
- Risques typiques : saisonnalité des inscriptions, concurrence des plateformes (Udemy, OpenClassrooms), pédagogie chronophage, administratif Qualiopi
- Opportunités IA : création de contenu pédagogique (modules, exercices, quiz), posts LinkedIn et articles SEO, automatisation des inscriptions et relances, génération de supports de cours, suivi personnalisé des élèves
- Pour ${employees} personne(s) : le contenu est votre produit — l'IA peut multiplier votre production par 5`,

    btp: `CONTEXTE SECTORIEL BTP & ARTISANAT :
- Enjeux clés : taux de conversion devis (10-30%), marge chantier, délais de paiement, gestion des sous-traitants
- Canaux critiques : téléphone (vital — clients appellent pour urgence), recommandation, Google Maps, PagesJaunes
- Risques typiques : appels manqués = chantiers perdus, devis chronophages, impayés, gestion planning complexe
- Opportunités IA : réception d'appels 24/7 avec qualification des urgences, génération de devis types, relance factures impayées, suivi de chantier automatisé, réponse aux avis Google`,

    saas: `CONTEXTE SECTORIEL SAAS & TECH :
- Enjeux clés : MRR growth rate (cible 10-20%/mois), churn rate (cible <5%), CAC payback (<12 mois), NPS
- Canaux critiques : content marketing (SEO, blog), Product Hunt, LinkedIn, outbound sales, partnerships
- Risques typiques : churn élevé, product-market fit incertain, concurrence US bien financée, burnout fondateur
- Opportunités IA : content marketing automatisé (articles, docs, landing pages), support client technique IA, analyse de churn et prédiction, prospection outbound ciblée, génération de code et documentation`,

    commerce: `CONTEXTE SECTORIEL COMMERCE LOCAL :
- Enjeux clés : panier moyen, fréquence de visite, taux de rétention, visibilité locale
- Canaux critiques : Google My Business, réseaux sociaux locaux, vitrine physique, SMS/WhatsApp
- Risques typiques : dépendance au passage physique, concurrence e-commerce, saisonnalité, trésorerie
- Opportunités IA : création de contenu local (posts, stories), réponse aux avis Google automatique, campagnes SMS personnalisées, gestion des stocks simplifiée, fidélisation automatisée`,

    freelance: `CONTEXTE SECTORIEL FREELANCE :
- Enjeux clés : taux journalier, pipeline de missions, temps non facturable (admin, prospection = 30-40%), diversification clients
- Canaux critiques : LinkedIn, plateformes (Malt, Upwork), recommandation, site portfolio
- Risques typiques : tout repose sur UNE personne, irrégularité revenus, pas de backup, admin qui tue la productivité
- Opportunités IA : prospection LinkedIn automatisée, facturation et relances automatiques, création de contenu portfolio, assistant admin (emails, devis, contrats), recherche de missions`,

    logistique: `CONTEXTE SECTORIEL LOGISTIQUE & TRANSPORT :
- Enjeux clés : taux de remplissage, coût au km, délais de livraison, satisfaction client (SLA)
- Canaux critiques : téléphone (urgences transport), email, plateformes (Chronopost, DHL), appels d'offres
- Risques typiques : appels urgents 24/7, optimisation tournées complexe, fluctuation prix carburant, litiges livraison
- Opportunités IA : gestion des appels urgents et suivi colis automatisé, optimisation de tournées, relation client proactive (alerte retard), analyse des coûts de transport`,

    finance: `CONTEXTE SECTORIEL FINANCE & ASSURANCE :
- Enjeux clés : coût d'acquisition client (CAC élevé), valeur vie client, conformité réglementaire (ACPR, AMF), taux de closing
- Canaux critiques : recommandation, networking, LinkedIn, événements professionnels
- Risques typiques : conformité réglementaire lourde, cycle de vente long, concurrence des néo-banques/assurtechs
- Opportunités IA : analyse de portefeuille et recommandations personnalisées, création de rapports financiers, conformité documentaire automatisée, prospection ciblée entreprises, support client réglementaire`,

    restauration: `CONTEXTE SECTORIEL RESTAURATION :
- Enjeux clés : taux de remplissage (midi/soir), panier moyen, note Google/ TripAdvisor (crucial), gestion des stocks/perte
- Canaux critiques : téléphone (réservations = 60%+ du CA), Google Maps, réseaux sociaux (Instagram), TheFork
- Risques typiques : appels pendant le service = injoignable, avis négatifs non répondus, gestion des stocks imprécise, turn-over staff
- Opportunités IA : prise de réservation téléphonique 24/7, réponse automatique aux avis, création de contenu Instagram, gestion des menus et suggestions personnalisées`,
  }

  return contexts[sector] || contexts.services
}
