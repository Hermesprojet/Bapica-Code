Documenter ton contenu
propriétaire — Guide Bapica
C'est ce contenu, et lui seul, qui différenciera Bapica
de SKL et de tout concurrent.
Une base générique, n'importe qui peut l'obtenir. Tes
cas réels, non.
Bonne nouvelle : 10 à 20 fiches bien faites suffisent à
changer la perception.
1. Template — Cas client
Le format le plus précieux. Chaque client
accompagné = une fiche.
{
  "agent_id": "prospection-strategie",
  "source": "Cas client - [secteur, ex: 
restaurant à Bruxelles]",
  "category": "cas-client",
  "content": "SITUATION DE DÉPART : [Quelle 
entreprise ? Taille, secteur, pays. Quel 
était son problème précis ? Chiffres si 
possible : CA, nombre de clients, marge.]
CE QUI BLOQUAIT : [Le vrai obstacle 
identifié, pas le symptôme. Ex: 'il pensait 
manquer de clients, mais le vrai problème 
était un ticket moyen trop bas'.]
CE QUI A ÉTÉ FAIT : [Les actions concrètes, 
dans l'ordre. Sois précis : quelles 
décisions, quels changements, en combien de 
temps.]
RÉSULTAT : [Le résultat mesurable. 
Chiffres, délai. Sois honnête, y compris 
sur ce qui n'a pas marché.]
LEÇON GÉNÉRALISABLE : [Ce qu'un autre 
dirigeant dans une situation similaire peut 
en retirer. C'est la partie que l'agent 
réutilisera.]"
}
Exemple rempli (fictif, à remplacer par tes vrais cas) :
SITUATION DE DÉPART : Restaurant familial à 
Bruxelles, 15 ans d'existence,
CA stable mais marge en baisse. 40 
couverts/jour en moyenne, ticket moyen 22 
€.
Le gérant voulait "plus de clients".
CE QUI BLOQUAIT : Le problème n'était pas 
la fréquentation (correcte pour le
quartier) mais le ticket moyen : aucune 
suggestion de boisson ou dessert,
carte trop large et peu lisible.
CE QUI A ÉTÉ FAIT : 1) Carte resserrée de 
24 à 14 plats. 2) Formation du
service à la suggestion systématique 
(entrée ou dessert + boisson).
3) Ajout de 2 menus à prix fixe mettant en 
avant les plats à forte marge.
Mise en place en 3 semaines.
RÉSULTAT : Ticket moyen passé de 22 € à 
28,50 € en 2 mois (+29 %), à
fréquentation identique. Marge nette 
améliorée. La carte réduite a aussi
baissé les pertes en cuisine.
LEÇON GÉNÉRALISABLE : Quand un dirigeant 
demande "plus de clients",
vérifier d'abord le ticket moyen : c'est 
souvent le levier le plus rapide,
sans coût d'acquisition. Une carte trop 
large dilue la marge et ralentit
la décision du client.
2. Template — Ta méthode maison
Ce que tu fais différemment des autres.
{
  "agent_id": "prospection-strategie",
  "source": "Méthode Bapica - [nom de ta 
méthode]",
  "category": "methode-maison",
  "content": "PRINCIPE : [En quoi consiste 
ta méthode, en une phrase.]
POURQUOI ELLE MARCHE : [Ta conviction, ton 
raisonnement. C'est ta valeur.]
COMMENT L'APPLIQUER : [Étapes concrètes.]
QUAND NE PAS L'UTILISER : [Les limites. Un 
conseiller honnête sur ses limites
est plus crédible qu'un conseiller 
universel.]"
}
3. Template — Question fréquente
réelle
Chaque question que tes utilisateurs posent souvent
= une fiche.
{
  "agent_id": "[l'agent concerné]",
  "source": "FAQ terrain - [la question]",
  "category": "faq-reelle",
  "content": "QUESTION POSÉE : [la 
formulation réelle des utilisateurs]
RÉPONSE : [Ta réponse, celle que tu 
donnerais vraiment.]
CE QUE LES GENS COMPRENNENT MAL : [Le 
malentendu fréquent sur ce sujet.]"
}
4. Comment collecter ce contenu
sans y passer des semaines
Le réflexe à prendre : après chaque interaction
significative, 10 minutes de documentation.
Source de
contenu
Comment la capter
Cas client
Après chaque accompagnement,
remplis le template (15 min)
Questions
récurrentes
Note les questions posées à tes
agents (logs) et documente les
réponses
Retours
utilisateurs
Chaque plainte ou compliment
révèle un sujet à documenter
Tes propres
décisions
Quand tu tranches un sujet
business, écris pourquoi
Astuce : tu peux dicter à voix haute (agent vocal !) et
faire structurer par Claude ensuite. La barrière est
souvent la page blanche, pas le manque de matière.
5. Ingestion
Une fois tes fiches écrites dans un fichier JSON
(même format que les autres) :
npx tsx scripts/ingest-knowledge.ts 
mes_cas_clients.json
Le point clé
Les ~140 fiches génériques que tu as déjà font de tes
agents des bons généralistes.
Tes cas réels en feront des experts reconnaissables.
Un utilisateur qui reçoit un conseil illustré par un cas
concret de PME belge
comme la sienne ne se dira pas "c'est une IA
générique" — il se dira
"ils connaissent mon métier". C'est ça, la différence.
