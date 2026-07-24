# Bapica — Référence du projet

> Fichier de contexte unique. Un agent (Claude Code ou l'agent QA) doit lire CE fichier
> avant de tester ou modifier Bapica, au lieu de re-parcourir tout le code.
> À tenir à jour quand l'architecture, les agents, les plans ou les capacités changent.

## 1. Ce qu'est Bapica

Bapica est une plateforme SaaS multi-agents IA pour PME et indépendants. Elle fournit **10 agents
IA spécialisés** qui **automatisent le contact et les tâches métier** — y compris **contacter et
répondre aux clients par téléphone et par email**, pas seulement organiser des données.

Positionnement à ne jamais contredire dans les réponses des agents :
- Bapica **n'est pas un simple CRM** ni un outil d'organisation passif.
- Plusieurs agents **agissent directement auprès des clients** de l'utilisateur.
- Réponse attendue si on demande « les agents peuvent-ils contacter/appeler/répondre aux
  clients par téléphone ou email ? » → **OUI**, en citant l'agent concerné.
- Réponse attendue si on demande « peuvent-ils se connecter à LinkedIn/Instagram/Facebook et
  publier ? » → **OUI** : Camille crée ET publie/programme le contenu sur les réseaux connectés
  (sur autorisation ; connexion via Paramètres → connexions).
- Interdits dans les réponses : « je ne peux pas contacter vos clients », « je ne peux pas me
  connecter à LinkedIn/Instagram/Facebook », « je ne peux pas publier », « je suis une IA de
  création, pas de publication », « c'est une limite volontaire », « vos clients ont besoin de
  vous parler à vous ».

- Site : bapica.com (prod Vercel : bapica-code.vercel.app)
- Multilingue : FR / EN / AR (détection automatique dans les prompts).

## 2. Stack technique

- **Next.js 14.2.35** (App Router, dossier `src/`), TypeScript strict.
- **Tailwind CSS**.
- **Supabase** : auth + base de données (Postgres). Schéma : `supabase-schema.sql`.
- **Stripe** : abonnements (checkout + portail + webhook).
- **Anthropic Claude** : moteur des agents (`@anthropic-ai/sdk`).
- **OpenAI** : embeddings pour le RAG.
- Intégrations optionnelles : Vapi (vocal), HeyGen/Runway (vidéo), Resend (email), Twenty (CRM), n8n.
- Déploiement : **Vercel, Root Directory = `bapica`** (l'app n'est pas à la racine du repo).

## 3. Les 10 agents (source : `src/lib/agents.ts`)

| id | Persona | Rôle | Formule min |
|----|---------|------|-------------|
| `general` | Léo | Agent Général (point d'entrée, aiguillage) | Essentiel |
| `support` | Sofia | Support Client — répond aux clients par chat/email 24/7 | Essentiel |
| `content` | Camille | Créateur de Contenu (SEO, posts, newsletters) | Essentiel |
| `prospection-strategie` | Marc | Conseiller Croissance & Prospection | Essentiel |
| `closer` | Nadia | Closer Vocal — appelle et qualifie les prospects | Essentiel |
| `telephone` | Hugo | Agent Téléphonique — standard, appels entrants | Pro |
| `accounting` | Claire | Comptabilité — factures, relances email, trésorerie | Pro |
| `video` | Maya | Créateur Vidéo IA | Essentiel |
| `recruiter` | Yanis | Recruteur IA | Essentiel |
| `legal` | Inès | Administratif & Juridique (info générale, pas de conseil perso) | Essentiel |

- **Prompts de rôle** (RÔLE / MÉTHODE / RÈGLES) : `src/lib/agent-prompts.ts`
  → injectés via `getSystemPromptForAgent(id)` dans `/api/chat` ET `/api/demo-chat`.
  Les prompts couvrent la **parité de capacités avec Limova** : les missions des 8 agents Limova
  (Tom→Hugo, Charly→Léo, Elio→Marc/Nadia, Julia→Inès, John→Camille/Maya, Rony→Yanis, Lou→Camille,
  Manue→Claire) sont dispatchées sur les 10 agents selon leur spécialité (bureautique email/agenda
  + documents pour Léo ; étiquetage/base de connaissance pour Hugo ; diagnostic commercial pour Marc ;
  contrats de travail + grille de salaire pour Yanis ; rentabilité + échéances + scénarios pour Claire ;
  pactes/reformulations/veille pour Inès ; multi-réseaux + brouillon pour Camille…).
- **Contenu marketing** des pages agents : `src/lib/agent-content.ts`.
- Règle : légal (Inès) et comptabilité (Claire) ne remplacent JAMAIS un professionnel.

## 4. Plans & tarifs (source : `src/lib/stripe.ts`)

- **Essentiel** — 49 €/mois — 8 agents.
- **Pro** — 79 €/mois — 10 agents, messages illimités.
- Essai gratuit : 15 jours. Appels vocaux facturés ~0,20 €/min.
- Variables prix : `STRIPE_PRICE_ESSENTIAL`, `STRIPE_PRICE_PRO`.

## 5. Routes API principales (`src/app/api/`)

| Route | Rôle | Auth |
|-------|------|------|
| `chat` | Chat des agents (dashboard, connecté) | Bearer token Supabase |
| `demo-chat` | Démo publique (3 messages, sans compte, modèle Haiku) | Aucune |
| `stripe/checkout` | Crée la session de paiement | userId côté client |
| `stripe/portal` | Portail de gestion d'abonnement | userId |
| `webhooks/stripe` | Met à jour le plan dans `profiles` (client service_role) | Signature Stripe |
| `vapi/create-call` | Lance un appel vocal sortant (Vapi) | Bearer token |
| `vapi/webhook` | Reçoit le résultat d'appel Vapi | — |
| `video/questions` | Maya — 3-5 questions de cadrage avant génération (Haiku) | Bearer token |
| `video/orchestrate` | Maya — idée (+ réponses) → package de production complet | Bearer token |
| `video/render` / `video/status` | Rendu réel des clips (Runway/HeyGen) + polling | Bearer token |
| `video/generate` | Rendu direct via moteur (Runway/HeyGen) — nécessite les clés | Bearer token |

(Autres routes : cortex, genesis, reason, business-analysis, market-intelligence, etc.)

## 6. Fichiers clés

- `src/lib/agents.ts` — définition des 10 agents (SOURCE DE VÉRITÉ des agents).
- `src/lib/agent-prompts.ts` — rôle/méthode/règles par agent.
- `src/lib/supabase.ts` / `supabase-admin.ts` — clients Supabase (lazy).
- `src/lib/stripe.ts` — client Stripe (lazy) + plans + `planFromPriceId`.
- `src/lib/rag.ts` — RAG (recherche de connaissances par agent, embeddings OpenAI).
- `src/lib/business-context.ts` — `buildBusinessBrief(onboarding)` : brief du business du client
  injecté dans le prompt de CHAQUE agent (secteur, taille, CA, défi, objectifs, outils + analyse).
  Source : `user_metadata.onboarding_data` (là où l'onboarding l'écrit).
- `src/app/api/chat/route.ts` — cœur du chat connecté (auth, mémoire, brief business, RAG, live data, tools).
- `src/app/api/demo-chat/route.ts` — démo publique.
- `src/lib/tools/*` — **vrais outils** exposés aux agents dans `/api/chat` : `consulter_agent`
  (collaboration inter-agents), `auditer_site` (**audit SEO** : titres/meta/OG/JSON-LD, images sans
  alt, liens internes/externes, hreflang, HTTPS, temps de réponse, robots.txt/sitemap, **score /100**),
  `rechercher_motscles` (**mots-clés réels** via Google Suggest, gratuit), `lire_emails`/`proposer_email`,
  `lire_plateforme`/`proposer_action` (lecture/écriture des plateformes connectées via
  `platform-call.ts`), `proposer_rdv` (**prise de RDV**), `proposer_document` (**produit un
  fichier** : PDF imprimable/Excel-CSV/Markdown → page `dashboard/documents`), `etiqueter_echange`
  (**tag persisté** prospect/SAV/impayé… → page `dashboard/tags`), `programmer_relances`
  (**échéancier d'impayés** J+7/J+15/J+30 → page `dashboard/reminders`), `proposer_sms`
  (**SMS Twilio**, compte rendu d'appel), `lire_banque` (**soldes/transactions réels** via
  GoCardless), et `twenty-tools` (CRM, réservé aux agents commerciaux). Chaque outil du chat a
  un handler dans `route.ts` (**14 outils = 14 handlers**, cohérence à préserver).
- **Actions à valider** (`src/lib/actions/store.ts` + `GET|POST /api/actions` + page
  `dashboard/actions`) : les agents **proposent** (email, action plateforme, RDV) ; rien n'est
  exécuté sans validation explicite de l'utilisateur. Table `pending_actions` (exécuter
  `supabase-schema.sql`).
- **Agenda / RDV** (`src/lib/calendar/providers.ts` + routes `/api/calendar/{google,outlook}/
  {connect,callback}`) : à la validation d'une action `calendar`, si le client a connecté
  **Google Calendar** ou **Outlook** (OAuth, page Connexions), l'événement est créé DIRECTEMENT
  dans son agenda (refresh de jeton automatique) ; sinon repli sur un **`.ics`** téléchargé côté
  client. Prérequis prod : `GOOGLE_CLIENT_ID`/`SECRET` et/ou `MICROSOFT_CLIENT_ID`/`SECRET`.
- **Documents / Étiquettes / Relances** : trois fonctions persistées (tables `deliverables`,
  `interaction_tags`, `payment_reminders` dans `supabase-schema.sql`) avec store service_role
  (`src/lib/{deliverables,tags,reminders}/store.ts`), routes `/api/{deliverables,tags,reminders}`
  et pages `dashboard/{documents,tags,reminders}`. Les relances envoient via une action email
  « à valider ». `deliverables.ts` construit les fichiers (CSV avec BOM, HTML imprimable, Markdown)
  sans dépendance binaire.
- **SMS** (`src/lib/sms.ts` + provider `sms` dans `/api/actions`) : envoi Twilio après validation.
  Prérequis prod : `TWILIO_ACCOUNT_SID`/`AUTH_TOKEN` + `TWILIO_SMS_NUMBER` (ou `TWILIO_MESSAGING_SERVICE_SID`).
- **Google Docs/Sheets** (`src/lib/google/workspace.ts` + routes `/api/google/workspace/{connect,
  callback}` + `POST /api/deliverables/[id]/google`) : export d'un document en Sheet (depuis le CSV)
  ou Doc (texte). OAuth Google (mêmes `GOOGLE_CLIENT_ID/SECRET`, APIs Drive/Docs/Sheets + redirection
  `/api/google/workspace/callback`).
- **Banque** (`src/lib/bank/gocardless.ts` + `/api/bank`) : connecteur GoCardless Bank Account Data
  (lecture seule, 2500+ banques EU). Flux : identifiants client (secret_id/key) → token → requisition
  (auth banque) → comptes → soldes/transactions. Aucune variable Vercel (identifiants par client).

## 7. Variables d'environnement

**Requises pour le fonctionnement de base :**
`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`,
`ANTHROPIC_API_KEY`, `NEXT_PUBLIC_APP_URL`.

**Paiement :** `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`,
`STRIPE_PRICE_ESSENTIAL`, `STRIPE_PRICE_PRO`.

**RAG / intégrations (optionnelles) :** `OPENAI_API_KEY` (embeddings), `VAPI_*` (vocal),
`HEYGEN_*` / `RUNWAY_API_KEY` (vidéo), `RESEND_API_KEY` (email), `TWILIO_*`, `N8N_*`.

Détail : `.env.example`.

## 8. Règles & pièges connus (IMPORTANT pour ne pas casser le build)

1. **Ne JAMAIS instancier Supabase/Stripe au niveau module.** `createClient(...)` / `new Stripe(...)`
   exécuté à l'import fait échouer le build Vercel (« supabaseUrl is required »,
   « collect page data » qui plante). Toujours **instanciation paresseuse** (dans une fonction,
   au runtime). Idem pour tout SDK qui lève une erreur si sa clé est absente.
2. **Auth des routes connectées** : le client envoie `Authorization: Bearer <access_token>`.
   Côté serveur, valider avec `supabase.auth.getUser(token)` — jamais `getUser()` sans argument
   (sinon 401 systématique).
3. **Versions de dépendances figées** (versions exactes dans `package.json`). Next.js 14.2.x.
4. **Modèles Claude valides uniquement** : `claude-sonnet-4-5`, `claude-haiku-4-5`,
   `claude-opus-4-1` (voir `resolveModel` / `optimizations.ts`). Pas d'ID inventé.
5. **Outils CRM (twentyTools)** réservés aux agents commerciaux (`prospection-strategie`,
   `closer`) — pas à l'agent général, sinon il se prend pour un CRM.
6. **Prompts** : ton pro et sobre, prose naturelle, pas d'émojis, pas de Markdown brut
   (les bulles n'affichent pas `**`/`#`).

## 9. Procédure de test / QA

Avant de conclure « ça marche », exécuter dans `bapica/` :

```bash
npm install
npx tsc --noEmit        # 0 erreur de type
npm run build           # doit finir EXIT 0 (surveiller "supabaseUrl is required")
```

Puis tests runtime (serveur local `npm run start` sur un PORT) :
- `/` → 200
- `/api/demo-chat` (POST `{message}`) → réponse ou 503 si pas de clé (jamais 500 non géré)
- `/api/chat` sans token → 401 ; avec token invalide → 401
- Pages agents `/agents/<id>` → 200 ; id inconnu → 404

Cohérence produit à vérifier dans les réponses des agents :
- « Les agents peuvent-ils contacter mes clients par téléphone/email ? » → doit répondre **OUI**
  en citant Sofia (chat/email), Hugo (téléphone), Nadia (appels), Claire (relances email).
- Chaque agent respecte son rôle (Marc demande le contexte avant de prospecter, Inès renvoie
  vers un avocat, Claire réclame les chiffres avant une prévision, etc.).

## 10bis. Design / thème (IMPORTANT)

- **Thème = CLAIR** (fond blanc, style épuré inspiré de Substi.ai). Ne pas réintroduire de fond sombre.
- Le système de couleurs vit dans `src/app/globals.css` : tokens HSL dans `:root` + classes custom
  (`card-professional`, `feature-card`, `pricing-card`, `agent-card`, `section-tinted`, `gradient-hero`,
  `gradient-text`, `btn-primary`…). Changer le thème = éditer CE fichier, pas chaque composant.
- Couleur primaire = bleu **#2563EB** (`--primary: 221 83% 53%`), texte **#111827**, accent teal **#0d9488**.
- La home (`src/app/page.tsx`) code ses couleurs en dur (blanc/#111827/#2563EB) et n'utilise PAS les
  composants `src/components/landing/*` (thème sombre, en grande partie orphelins) — seuls Navbar/Footer
  en sont importés.
- Exceptions volontairement sombres (bandeaux d'accent sur page claire) : sections `Chiffres`/`CTAFinal`
  de la home, le slideshow `video-presentation.tsx`.

## 10ter. Maya — Studio Vidéo (cerveau d'orchestration)

- Maya = directrice créative IA. Le « cerveau » (`src/lib/video/maya.ts`) transforme une idée en
  **package de production** JSON : concept, hook, storyboard scène par scène (décor/lumière/caméra/
  mouvement/émotion/dialogue/SFX/durée), **prompt visuel prêt par moteur**, voix/musique/sous-titres,
  formats, CTA, titre, description, hashtags. Route : `POST /api/video/orchestrate` (Bearer + Claude Sonnet).
- Routeur multi-moteurs (dans le prompt) : avatar→HeyGen, cinématique→Runway, ultra-réaliste→Veo,
  stylisé→Kling, motion→Luma. Maya ne REND pas de MP4 depuis le cerveau ; le rendu est une couche à part.
- **Rendu réel** (`src/lib/video/engines.ts`) : Runway (texte→image→vidéo, 2 étapes), HeyGen (avatar parlant),
  ElevenLabs (voix off). Routes `POST /api/video/render` (action `scene`|`animate`|`voice`) et
  `POST /api/video/status` (polling). ÉCRIT À L'AVEUGLE (non testable en sandbox : pas de clés + réseau
  bloqué) → les erreurs moteurs sont remontées brutes pour le débogage en prod. Peut nécessiter un
  ajustement des paramètres d'API au 1er test réel.
- Clés requises en prod pour le rendu : `RUNWAY_API_KEY` ; `HEYGEN_API_KEY` + `HEYGEN_AVATAR_ID` +
  `HEYGEN_VOICE_ID` ; `ELEVENLABS_API_KEY` (+ `ELEVENLABS_VOICE_ID` optionnel).
- **Capacités avancées (engines.ts)** — écrites à l'aveugle, mêmes clés HeyGen :
  - **Avatar depuis une photo** : `heygenUploadTalkingPhoto` + `heygenTalkingPhotoVideo` →
    route `POST /api/video/avatar` (`create` puis `generate`, suivi via `/api/video/status`).
  - **Traduction/doublage lip-sync** : `heygenTranslateVideo`/`heygenTranslateStatus` →
    route `POST /api/video/translate` (`start`/`status`).
- **Montage/édition cloud** : `src/lib/video/editor.ts` (Shotstack : timeline → MP4, marche en
  serverless contrairement à FFmpeg) → route `POST /api/video/edit` (`start`/`status`). Clé
  `SHOTSTACK_API_KEY` (`SHOTSTACK_ENV`='v1' par défaut). La route FFmpeg `/api/video/assemble`
  reste (nécessite un hôte avec FFmpeg — Railway/Fly.io) mais Shotstack est la voie serverless.
- UI : `dashboard/video-studio` (thème clair) — brief → `ProductionPackageView`
  (`src/components/agents/production-package.tsx`), avec « Générer le clip » par scène + « Générer la voix off ».

## 10quater. Connexions réseaux sociaux (publication)

- Objectif : Camille publie sur les réseaux du client. Approche **native, plateforme par
  plateforme** (choix utilisateur) — **LinkedIn branché en premier**, les autres à suivre.
- LinkedIn (OAuth 2.0 + publication) : `src/lib/social/linkedin.ts` (authorize / token / userinfo /
  ugcPosts). Écrit « à l'aveugle » (non testé) → nécessite en prod une app LinkedIn avec les produits
  « Sign In with LinkedIn using OpenID Connect » + « Share on LinkedIn », l'URL de redirection déclarée,
  et `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET`.
- Stockage des jetons : table **`social_connections`** (voir `supabase-schema.sql`) via
  `getSupabaseAdmin()` (service_role) — `src/lib/social/store.ts`. RLS activée sans policy.
- Routes : `GET /api/social/linkedin/connect?t=<token>` (redirige vers LinkedIn),
  `GET /api/social/linkedin/callback` (échange + enregistre), `POST /api/social/publish`
  `{text, platforms}`, `GET|DELETE /api/social/accounts`.
- UI : `dashboard/connections` (lien sidebar « Connexions ») — connecter/déconnecter + composer
  « Publier sur LinkedIn ».
- Auth des routes : Bearer Supabase (helper `src/lib/api-auth.ts`). L'OAuth (navigation plein écran)
  passe le jeton en query `?t=` puis n'encode que l'`uid` dans le `state` (le jeton ne va pas à LinkedIn).
- Ajouter une plateforme : nouveau module `src/lib/social/<x>.ts` + branche dans `/api/social/publish`.

## 10quinquies. RAG documentaire (connaissance du client)

- Deux niveaux de RAG :
  - **Global (les 140 fichiers)** : `src/lib/rag.ts`, table `growth_knowledge`, scopé par AGENT
    (RPC `match_agent_knowledge`). Ingestion via `scripts/ingest-knowledge.ts`.
  - **Par client** : `src/lib/client-knowledge.ts`, table `client_knowledge`, scopé par UTILISATEUR
    (RPC `match_client_knowledge`). Les documents que le client téléverse deviennent sa base propre,
    injectée dans le prompt de CHAQUE agent (bloc « Documents de l'entreprise du client »).
- Extraction : PDF (`pdf-parse/lib/pdf-parse.js`), DOCX (`mammoth`), texte brut. Embeddings OpenAI
  `text-embedding-3-small` (1536 dims). Écrit à l'aveugle (non testé) → prérequis prod :
  `OPENAI_API_KEY` + exécuter le SQL (`supabase-schema.sql` : extension `vector`, table
  `client_knowledge`, RPC `match_client_knowledge`).
- Routes : `POST /api/knowledge/upload` (fichier multipart OU {title,text}), `GET|DELETE /api/knowledge`.
- UI : `dashboard/knowledge` (lien sidebar « Connaissances ») — téléverser / coller / lister / supprimer.

## 10sexies. Recherche internet sur l'entreprise

- `src/lib/company-research.ts` : lit le site web du client (`fetchWebsiteText`) + recherche web
  (`webSearch`, SerpAPI si `SERPAPI_KEY`), puis Claude (Sonnet) rédige un profil factuel.
- Route `POST /api/company/research` : lit le profil onboarding (user_metadata), lance la recherche,
  et stocke le résumé comme document `client_knowledge` (« Recherche web — <société> ») → utilisable
  par les agents via le RAG. Écrit à l'aveugle. Clés : `ANTHROPIC_API_KEY` (requis), `SERPAPI_KEY`
  (optionnel — sans, seul le site web est lu), `OPENAI_API_KEY` (pour stocker dans le RAG).
- UI : bouton « Lancer la recherche » sur `dashboard/knowledge`.

## 10septies. Canaux de messagerie (WhatsApp / Telegram / Messenger)

- Objectif : rendre les agents joignables sur les messageries. Backend **entièrement codé** :
  `src/lib/omnichannel.ts` (webhooks + routage vers le bon agent + envoi) et le webhook UNIQUE
  `POST /api/webhooks/messaging` (auto-détection de la plateforme). `routeMessage` route par mots-clés
  vers un agent existant (les intentions « analyse/rapport » → `accounting`).
- Statut & guide : page `dashboard/channels` (lien sidebar « Canaux ») + route
  `GET /api/channels/status` (Bearer) qui renvoie des booléens de présence des jetons — **jamais leur
  valeur**. Affiche l'URL de webhook commune (`<APP_URL>/api/webhooks/messaging`).
- **À activer en prod** (variables Vercel, puis redéploiement + enregistrement du webhook) :
  WhatsApp (`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_VERIFY_TOKEN`),
  Telegram (`TELEGRAM_BOT_TOKEN` + `setWebhook`), Messenger (`MESSENGER_PAGE_TOKEN`,
  `MESSENGER_VERIFY_TOKEN`), et `NEXT_PUBLIC_APP_URL` (le webhook rappelle `/api/demo-chat`).
- Sans jetons : `sendWhatsApp/Telegram/Messenger` renvoient `false` proprement (pas de crash).
- **WhatsApp via Twilio** (voie simplifiée, sans Meta Developers) : `TWILIO_ACCOUNT_SID`,
  `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER` (ex `whatsapp:+14155238886`, sandbox Twilio pour
  tester). Le webhook détecte le POST **form-urlencoded** de Twilio et répond via l'API Twilio
  (`handleTwilioWhatsApp` / `sendTwilioWhatsApp` dans `omnichannel.ts`, `metadata.via='twilio'`).
  URL de webhook à coller dans Twilio (« When a message comes in », POST) = `<APP_URL>/api/webhooks/messaging`.
- **Hub multi-client Telegram** (chaque client = son propre bot, sans variable Vercel) :
  - Table `channel_connections` (`supabase-schema.sql`) : `{user_id, platform, credentials(jsonb),
    external_id, webhook_secret}`. Store service_role : `src/lib/channels/store.ts`
    (`saveChannel`/`getChannelBySecret`/`getChannel`/`deleteChannel`).
  - `POST /api/channels/telegram/connect` (Bearer) : valide le jeton (getMe), génère un `secret`,
    **stocke** `{botToken}` + secret, puis `setWebhook?...&secret_token=<secret>`. `GET`/`DELETE` =
    état / déconnexion. UI `dashboard/channels` (connecté @bot + Déconnecter ; « base non initialisée »
    si le SQL n'a pas été exécuté).
  - Réception : le webhook lit l'en-tête `X-Telegram-Bot-Api-Secret-Token` → `getChannelBySecret` →
    `user_id` + `botToken`. Réponse via le bot du client (`sendTelegram(chatId, text, botToken)`) et
    contexte de SON entreprise via `replyForUser(userId, agentId, text)` (`src/lib/channels/agent-reply.ts`,
    réutilise `buildBusinessBrief` + `getSystemPromptForAgent`).
  - **Repli** : sans secret/connexion, comportement mono-bot conservé (`TELEGRAM_BOT_TOKEN` +
    `demo-chat`) → pas de régression. **Prérequis** : exécuter `supabase-schema.sql`.
- **Hub multi-client WhatsApp** (socle FAIT, connexion client À FAIRE) :
  - **Fait** : `sendWhatsApp(to, text, {token, phoneId})` utilise les identifiants DU CLIENT ;
    le webhook résout le locataire via `msg.metadata.phoneId` (= `phone_number_id` de l'API Cloud,
    déjà extrait par `handleWhatsAppWebhook`) → `getChannelByExternal('whatsapp', phoneId)` →
    réponse avec le token du client + `replyForUser` (contexte de son entreprise).
    Repli mono-locataire conservé (variables globales) si non résolu.
  - **Reste à faire — Embedded Signup** (décision produit : le client garde SON numéro, sans jamais
    voir Facebook Developers) :
    1. Prérequis business (côté utilisateur, délai de plusieurs jours) : compte **Meta Business** +
       **vérification d'entreprise** + App Meta (type Business) avec produit **WhatsApp** +
       configuration **Embedded Signup**.
    2. Variables à obtenir puis mettre dans Vercel : `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`,
       `WHATSAPP_CONFIG_ID`.
    3. À coder ensuite : bouton « Connecter WhatsApp » (SDK JS Meta, popup `configuration_id`) →
       renvoie un `code` → route d'échange côté serveur (code → token client, WABA id,
       `phone_number_id`) → `saveChannel(userId, 'whatsapp', { credentials: { accessToken },
       externalId: phone_number_id })` → abonner le numéro au webhook de l'app.
       Dès cet enregistrement, la plomberie ci-dessus fonctionne sans autre changement.
  - Alternative écartée pour l'instant : Twilio ISV / 360dialog Partner (même principe, autre
    fournisseur). Twilio reste branché en **mono-numéro** pour les tests (sandbox).
  - Diagnostic : `POST /api/channels/whatsapp/test` (Bearer) + bouton « Tester l'envoi WhatsApp »
    dans `dashboard/channels` → renvoie l'**erreur Twilio exacte** (ex. `20003 Authenticate` =
    mauvais `TWILIO_AUTH_TOKEN`).

## ⚠️ Piège de déploiement (rencontré 2 fois)
Après avoir ajouté une variable d'environnement dans Vercel, **ne jamais cliquer « Redeploy » sur un
ancien déploiement de la liste** : cela remet CE code-là en production et fait disparaître les
fonctionnalités récentes (symptôme : une route récente répond 404, ou un champ de réponse a disparu).
Toujours redéployer **le déploiement le plus récent**, ou pousser un commit (même vide) pour forcer
un déploiement propre du dernier code.

## 10. Déploiement

- Branche de dev : `claude/hopeful-gates-nucb4p` → PR → merge dans `master` → Vercel déploie.
- Vérifier après déploiement que le build Vercel est **Ready** (pas seulement le build local).
- Si un agent « ne répond pas » : d'abord vérifier que le **build Vercel a réussi** (souvent la
  vraie cause), puis les variables d'env (`ANTHROPIC_API_KEY`, Supabase).

## 11. ⚠️ À activer en prod (le code est prêt, il manque les clés/SQL)

Plusieurs fonctions sont **entièrement codées** mais dormantes tant que leurs variables ne sont pas
renseignées dans **Vercel (Environment Variables)** et, pour le RAG, tant que
**`bapica/supabase-schema.sql`** n'a pas été exécuté (Supabase → SQL Editor). Tableau récapitulatif :

| Fonction | À configurer |
|---|---|
| Chat des agents (base) | `ANTHROPIC_API_KEY`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `NEXT_PUBLIC_APP_URL` |
| Paiement | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`, `STRIPE_PRICE_ESSENTIAL`, `STRIPE_PRICE_PRO` |
| RAG documentaire + recherche web (stockage) | `OPENAI_API_KEY` + **exécuter `supabase-schema.sql`** (extension `vector`, tables `client_knowledge`/`social_connections`, RPC de recherche) |
| Recherche internet sur l'entreprise | `SERPAPI_KEY` (optionnel — sans, seul le site web du client est lu) |
| Vidéo (rendu réel) | `RUNWAY_API_KEY` ; `HEYGEN_API_KEY` + `HEYGEN_AVATAR_ID` + `HEYGEN_VOICE_ID` ; `ELEVENLABS_API_KEY` |
| Publication LinkedIn | app LinkedIn (« Sign In with LinkedIn using OpenID Connect » + « Share on LinkedIn ») + `LINKEDIN_CLIENT_ID`/`LINKEDIN_CLIENT_SECRET` + URL de redirection `/api/social/linkedin/callback` |
| Canaux messagerie | WhatsApp (`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_VERIFY_TOKEN`) ; Telegram (`TELEGRAM_BOT_TOKEN` + `setWebhook`) ; Messenger (`MESSENGER_PAGE_TOKEN`, `MESSENGER_VERIFY_TOKEN`) — voir §10septies |

**Comportement sans clé = propre** : les routes renvoient un message « en cours de configuration »
(503 / erreur claire), jamais un crash. Au 1er test réel, si une fonction échoue, **récupérer le
message d'erreur brut affiché** (il remonte l'erreur du service) et ajuster. Détail des variables :
`bapica/.env.example`.

**Diagnostic des variables** : registre central `src/lib/env.ts` (groupes par fonction + `checkEnv()`,
présence uniquement — jamais les valeurs) ; `.env.example` est aligné dessus. Route admin
`GET /api/health/env` (Bearer + email dans `NEXT_PUBLIC_ADMIN_EMAILS`) → renvoie ce qui est
configuré/manquant en prod, à consulter après un déploiement.
