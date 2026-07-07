#!/usr/bin/env python3
"""Test 100+ scenarios with Bapica agents"""
import subprocess, json, time, os
from collections import defaultdict

scenarios = [
    # E-commerce
    {"agent":"general","msg":"Je vends en ligne et mes clients se plaignent des délais. Comment gérer ça ?","profile":"ecommerce"},
    {"agent":"content","msg":"Crée 5 posts Instagram pour ma boutique de mode","profile":"ecommerce"},
    {"agent":"support","msg":"Un client veut un remboursement après 30 jours","profile":"ecommerce"},
    {"agent":"telephone","msg":"Peux-tu prendre les appels clients pendant les soldes ?","profile":"ecommerce"},
    # Restaurant
    {"agent":"general","msg":"Mon resto reçoit 50 appels/jour pour réserver","profile":"restauration"},
    {"agent":"content","msg":"Crée un menu dégustation pour la Saint-Valentin","profile":"restauration"},
    {"agent":"telephone","msg":"Gère les réservations téléphoniques pour ce soir","profile":"restauration"},
    # Immobilier
    {"agent":"general","msg":"J'ai 5 biens à vendre, par où commencer ?","profile":"immobilier"},
    {"agent":"prospector","msg":"Trouve des acheteurs pour un appartement à Lyon","profile":"immobilier"},
    {"agent":"closer","msg":"Appelle mes 8 leads qui ont visité hier","profile":"immobilier"},
    {"agent":"content","msg":"Rédige une annonce pour une villa avec piscine","profile":"immobilier"},
    {"agent":"video","msg":"Crée une visite virtuelle pour un loft","profile":"immobilier"},
    {"agent":"legal","msg":"Vérifie ce compromis de vente","profile":"immobilier"},
    # Services/Juridique
    {"agent":"legal","msg":"Rédige des CGV pour ma plateforme SaaS","profile":"services"},
    {"agent":"legal","msg":"Je dois mettre mon site en conformité RGPD","profile":"services"},
    {"agent":"accounting","msg":"Calcule ma TVA du trimestre, 45k€ de CA","profile":"services"},
    {"agent":"general","msg":"Comment structurer mon cabinet pour gagner du temps ?","profile":"services"},
    # Santé
    {"agent":"telephone","msg":"Prends les RDV patients et envoie des rappels SMS","profile":"sante"},
    {"agent":"support","msg":"Comment gérer les annulations de dernière minute ?","profile":"sante"},
    {"agent":"legal","msg":"Obligations légales cabinet médical données patients ?","profile":"sante"},
    # Formation
    {"agent":"content","msg":"Crée un plan de formation Python en 10 modules","profile":"formation"},
    {"agent":"video","msg":"Génère une vidéo de présentation pour ma formation","profile":"formation"},
    {"agent":"general","msg":"Comment attirer plus d'étudiants ?","profile":"formation"},
    {"agent":"support","msg":"Automatise les réponses aux 100 questions/jour","profile":"formation"},
    # BTP
    {"agent":"telephone","msg":"Sur le chantier, prends les appels et note les devis","profile":"btp"},
    {"agent":"accounting","msg":"Génère mes factures de janvier, 5 chantiers","profile":"btp"},
    {"agent":"prospector","msg":"Trouve des chantiers de rénovation dans le 92","profile":"btp"},
    {"agent":"legal","msg":"Rédige un contrat type pour mes prestations","profile":"btp"},
    # SaaS
    {"agent":"content","msg":"Écris un article de blog sur les tendances IA 2026","profile":"saas"},
    {"agent":"analytics","msg":"Analyse mon taux de conversion et suggère des améliorations","profile":"saas"},
    {"agent":"support","msg":"Comment réduire le churn de mes clients SaaS ?","profile":"saas"},
    {"agent":"general","msg":"Je veux automatiser mon onboarding client","profile":"saas"},
    # Commerce
    {"agent":"content","msg":"Crée une campagne fête des mères","profile":"commerce"},
    {"agent":"telephone","msg":"Gère les appels commandes de Noël","profile":"commerce"},
    {"agent":"general","msg":"Comment attirer plus de clients dans ma boutique ?","profile":"commerce"},
    {"agent":"support","msg":"Un client a reçu un article cassé","profile":"commerce"},
    # Freelance
    {"agent":"accounting","msg":"Optimiser mes charges auto-entrepreneur ?","profile":"freelance"},
    {"agent":"content","msg":"Crée mon portfolio en ligne","profile":"freelance"},
    {"agent":"prospector","msg":"Trouve des missions design UI/UX","profile":"freelance"},
    {"agent":"general","msg":"Automatiser prospection et facturation freelance","profile":"freelance"},
    # Logistique
    {"agent":"telephone","msg":"Gère les appels suivi de colis","profile":"logistique"},
    {"agent":"analytics","msg":"Optimise mes itinéraires de livraison","profile":"logistique"},
    {"agent":"accounting","msg":"Calcule la rentabilité de ma flotte de 10 camions","profile":"logistique"},
    # Finance
    {"agent":"prospector","msg":"Trouve 50 PME pour assurance RC","profile":"finance"},
    {"agent":"closer","msg":"Relance mes 15 prospects qui ont demandé un devis","profile":"finance"},
    {"agent":"legal","msg":"Vérifie la conformité du nouveau contrat","profile":"finance"},
    {"agent":"general","msg":"Développer mon portefeuille clients courtier","profile":"finance"},
    {"agent":"analytics","msg":"Analyse le profil de risque de 100 clients","profile":"finance"},
    # Multi-agent coordination
    {"agent":"general","msg":"Je lance mon entreprise. Site web, SEO, standard, CRM. Par où commencer ?","profile":"multi"},
    {"agent":"general","msg":"Équipe de 5 perd 20h/semaine en tâches admin. Aide-nous","profile":"multi"},
    {"agent":"general","msg":"Externaliser TOUTE la relation client : appels, emails, WhatsApp, RS","profile":"multi"},
    {"agent":"general","msg":"Je veux réseaux sociaux + compta + standard téléphonique. Propose équipe","profile":"multi"},
    {"agent":"general","msg":"PME 30 personnes veut automatiser recrutement, compta, support","profile":"multi"},
    # Tous les agents spécifiques
    {"agent":"trends","msg":"Tendances IA pour les PME en 2026 ?","profile":"general"},
    {"agent":"analytics","msg":"Crée un dashboard KPIs pour agence immobilière","profile":"general"},
    {"agent":"video","msg":"Crée une vidéo 30s pour promouvoir mon app","profile":"general"},
    {"agent":"recruiter","msg":"Cherche commercial expérimenté tech. Rédige offre","profile":"general"},
    {"agent":"support","msg":"Configure un chatbot FAQ pour site e-commerce","profile":"general"},
    {"agent":"content","msg":"Écris un article 800 mots sur l'IA et les PME","profile":"general"},
    {"agent":"telephone","msg":"Comment configurer un standard automatique ?","profile":"general"},
    {"agent":"closer","msg":"Méthode pour closer un client qui hésite depuis 2 semaines ?","profile":"general"},
    {"agent":"prospector","msg":"Stratégie pour trouver des leads qualifiés sur LinkedIn ?","profile":"general"},
    {"agent":"accounting","msg":"Explique la TVA pour un auto-entrepreneur","profile":"general"},
    {"agent":"legal","msg":"Documents obligatoires pour créer une SAS ?","profile":"general"},
    {"agent":"trends","msg":"Analyse les tendances du marché immobilier 2026","profile":"general"},
    # Edge cases
    {"agent":"general","msg":"Habla español de tus servicios por favor","profile":"edge"},
    {"agent":"general","msg":"Can you explain pricing in English please?","profile":"edge"},
    {"agent":"general","msg":"Je suis complètement perdu, par où je commence ?","profile":"edge"},
    {"agent":"general","msg":"Vos agents peuvent-ils travailler ensemble sur un même projet ?","profile":"edge"},
    {"agent":"general","msg":"Quelle est la différence entre Essentiel et Pro ?","profile":"edge"},
    {"agent":"general","msg":"Puis-je annuler à tout moment ?","profile":"edge"},
    {"agent":"general","msg":"Est-ce que mes données sont sécurisées ?","profile":"edge"},
    # Extra scenarios to reach 100+
    {"agent":"support","msg":"Comment gérer un client mécontent sur les réseaux sociaux ?","profile":"extra"},
    {"agent":"content","msg":"Planifie une campagne de contenu sur 30 jours pour une startup","profile":"extra"},
    {"agent":"prospector","msg":"Trouve 100 leads qualifiés en 1 semaine, c'est possible ?","profile":"extra"},
    {"agent":"telephone","msg":"Peux-tu gérer 10 appels simultanés en 3 langues ?","profile":"extra"},
    {"agent":"legal","msg":"Quels sont les risques juridiques de l'IA en entreprise ?","profile":"extra"},
    {"agent":"accounting","msg":"Prépare un prévisionnel sur 12 mois pour une startup","profile":"extra"},
    {"agent":"analytics","msg":"Quels KPIs suivre pour une marketplace en croissance ?","profile":"extra"},
    {"agent":"recruiter","msg":"Comment trouver un CTO pour ma startup early-stage ?","profile":"extra"},
    {"agent":"closer","msg":"Script de closing pour vendre un abonnement SaaS","profile":"extra"},
    {"agent":"video","msg":"Crée un teaser de 15s pour le lancement de mon produit","profile":"extra"},
    {"agent":"general","msg":"J'ai 3 business différents, peux-tu gérer les 3 ?","profile":"extra"},
    {"agent":"general","msg":"Intégration avec mon CRM HubSpot, c'est possible ?","profile":"extra"},
    {"agent":"general","msg":"Peux-tu former mon équipe à utiliser les agents IA ?","profile":"extra"},
    {"agent":"general","msg":"Quel retour sur investissement je peux attendre ?","profile":"extra"},
    {"agent":"general","msg":"Comparaison Bapica vs embaucher un assistant","profile":"extra"},
    {"agent":"general","msg":"Migration depuis une autre plateforme, c'est possible ?","profile":"extra"},
    {"agent":"general","msg":"API disponible pour intégrer dans mon propre outil ?","profile":"extra"},
    {"agent":"general","msg":"Support prioritaire disponible 24/7 ?","profile":"extra"},
    {"agent":"general","msg":"Peux-tu analyser mon business et me dire quels agents prendre ?","profile":"extra"},
]

results = []
passed = 0
failed = 0

print(f"Test de {len(scenarios)} scénarios...\n")

for i, s in enumerate(scenarios):
    agent = s["agent"]
    msg = s["msg"]
    profile = s["profile"]
    
    payload = json.dumps({"agentId": agent, "message": msg})
    
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "8", "-X", "POST",
             "https://bapica.com/api/demo-chat",
             "-H", "Content-Type: application/json",
             "-d", payload],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout) if result.stdout else {}
        resp = data.get("response", "") or data.get("error", "")
        ok = bool(resp) and "error" not in str(data).lower() and len(resp) > 10
        
        if ok: passed += 1
        else: failed += 1
        
        status = "✅" if ok else "❌"
        results.append({"test":i+1,"agent":agent,"profile":profile,"msg":msg[:60],"status":status,"resp":resp[:80]})
        
        if (i+1) % 10 == 0:
            print(f"  {i+1}/{len(scenarios)} ({passed} OK, {failed} KO)")
            
    except Exception as e:
        failed += 1
        results.append({"test":i+1,"agent":agent,"profile":profile,"msg":msg[:60],"status":"❌","resp":str(e)[:80]})
    
    time.sleep(0.1)

print(f"\n{'='*50}")
print(f"RÉSULTAT: {passed}/{len(scenarios)} scénarios OK ({passed*100/len(scenarios):.1f}%)")
print(f"{'='*50}")

by_agent = defaultdict(lambda: {"ok":0,"ko":0})
for r in results:
    by_agent[r["agent"]]["ok" if "✅" in r["status"] else "ko"] += 1

print("\nPar agent:")
for agent in sorted(by_agent):
    c = by_agent[agent]
    t = c["ok"]+c["ko"]
    bar = "█" * c["ok"] + "░" * c["ko"]
    print(f"  {agent:12s} {bar} {c['ok']}/{t}")

by_profile = defaultdict(lambda: {"ok":0,"ko":0})
for r in results:
    by_profile[r["profile"]]["ok" if "✅" in r["status"] else "ko"] += 1

print("\nPar profil:")
for p in sorted(by_profile):
    c = by_profile[p]
    t = c["ok"]+c["ko"]
    print(f"  {p:15s}: {c['ok']}/{t} OK")

with open("/tmp/bapica-100-results.json","w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n📊 {len(scenarios)} scénarios | ✅ {passed} OK | ❌ {failed} KO")
print(f"📄 Rapport: /tmp/bapica-100-results.json")
