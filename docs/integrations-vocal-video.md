# Intégrations des Agnets Vocaux et Vidéo

## Guide complet de connexion pour la plateforme Hermes SaaS

---

## 1. AGENT TÉLÉPHONIQUE (Standard vocal) + CLOSER VOCAL

### Architecture
```
Appel entrant → Twilio → Vapi → Agent IA → Réponse vocale
                                 ↓
                          Webhook → Ta plateforme (logs, transcriptions)
```

### Stack nécessaire

| Service | À faire | Lien | Coût |
|---|---|---|---|
| **Vapi** | Créer un assistant vocal avec le prompt de l'agent | [vapi.ai](https://vapi.ai) | 0.07€/min |
| **Twilio** | Acheter un numéro, le connecter à Vapi | [twilio.com](https://twilio.com) | ~1€/mois + 0.014€/min |
| **ElevenLabs** | (Optionnel) Voix plus naturelle FR/EN/AR | [elevenlabs.io](https://elevenlabs.io) | 5$/mois (Starter) |

### Procédure pas à pas

#### Étape 1 : Créer un compte Vapi
1. Va sur https://vapi.ai → "Sign up"
2. Une fois connecté, va sur **Assistants → Create Assistant**
3. Configure l'assistant :
   - **Name** : "Standard Téléphonique" ou "Closer Commercial"
   - **System Prompt** :
     ```
     Copie tout le contenu du fichier :
     /workspace/hermes-saas/agents/prompts/agent-06-agent-telephonique.md
     ```
   - **Model** : `gpt-4o-mini` (recommandé pour la voix — rapide et pas cher)
   - **Voice** : Choisis une voix. Pour le français, prends ElevenLabs "Mathieu" ou "Léa"
   - **Language** : "Auto-detect"
   - **Max Duration** : 10 minutes
4. Note le **Assistant ID** → tu en auras besoin pour le .env.local

#### Étape 2 : Créer un numéro Twilio et le lier à Vapi
1. Va sur https://twilio.com → "Sign up" (gratuit, crédit de 15$ offert)
2. Va dans **Console → Phone Numbers → Buy a number**
   - Filtre par pays → France (+33)
   - Achète un numéro (le moins cher, ~1$/mois)
3. Dans Vapi → **Settings → Phone Numbers → Add Number**
   - Colle le numéro acheté
   - Colle ton **Account SID** et **Auth Token** Twilio
   - Vapi configure automatiquement le webhook Twilio

#### Étape 3 : Configurer le webhook sur ta plateforme
Les routes API sont déjà créées dans le projet :
- `POST /api/vapi/webhook` → reçoit les événements d'appel
- `POST /api/vapi/create-call` → lance un appel depuis la plateforme

Ajoute ces variables dans ton `.env.local` :
```bash
VAPI_API_KEY=ta_cle_vapi
VAPI_ASSISTANT_ID=id_de_lassistant
TWILIO_ACCOUNT_SID=ton_account_sid
TWILIO_AUTH_TOKEN=ton_auth_token
TWILIO_PHONE_NUMBER=ton_numero
```

#### Test
1. Va dans ton dashboard Vapi → **Playground**
2. Clique "Start call" ou appelle ton numéro Twilio
3. L'agent répond avec le prompt de l'agent téléphonique 🤖

---

## 2. CRÉATEUR VIDÉO IA (HeyGen + Runway)

### Stack nécessaire

| Service | Rôle | Lien | Coût |
|---|---|---|---|
| **HeyGen** | Avatars IA parlants (visage qui parle) | [heygen.com](https://heygen.com) | 24$/mois (Creator) |
| **Runway** | Génération vidéo (scènes, animations) | [runwayml.com](https://runwayml.com) | 15$/mois (Standard) |
| **ElevenLabs** | Voix off multilingue | [elevenlabs.io](https://elevenlabs.io) | 5$/mois (Starter) |

### Architecture
```
Ta plateforme → API HeyGen → Avatar IA qui parle
             → API Runway  → Scènes vidéo générées
             → ElevenLabs  → Doublage voix (FR/EN/AR)
```

### Procédure HeyGen

#### Étape 1 : Créer un compte
1. https://heygen.com → "Get Started" → Plan Creator (24$/mois)
2. **API → Create API Key** → note ta clé
3. **Avatars → Choisis un avatar** qui supporte le français

#### Étape 2 : Utiliser la route API déjà créée
```bash
POST /api/video/generate
```
Body :
```json
{
  "script": "Bonjour, je suis votre assistant IA...",
  "avatarId": "default",
  "language": "fr",
  "title": "Ma vidéo"
}
```

#### Étape 3 : Interface utilisateur
Un composant prêt à l'emploi existe :
```
components/agents/video-generator.tsx
```

---

## 3. RÉCAPITULATIF DES COMPTES À CRÉER

| # | Service | URL | Plan | Coût | Temps |
|---|---|---|---|---|---|
| 1 | **Supabase** | supabase.com | Free | 0€ | 3 min |
| 2 | **Stripe** | stripe.com | Free | 0€ | 5 min |
| 3 | **Claude API** | console.anthropic.com | Pay-as-you-go | ~5€ | 2 min |
| 4 | **Vercel** | vercel.com | Free | 0€ | 2 min |
| 5 | **Vapi** | vapi.ai | Pay-as-you-go | 0.07€/min | 10 min |
| 6 | **Twilio** | twilio.com | Free + crédit 15$ | ~1€/mois | 5 min |
| 7 | **ElevenLabs** | elevenlabs.io | Starter | 5$/mois | 2 min |
| 8 | **HeyGen** | heygen.com | Creator | 24$/mois | 5 min |
| 9 | **Runway** | runwayml.com | Standard | 15$/mois | 2 min |
| 10 | **n8n** | n8n.io (self-hosted) | Free | 0€ | 10 min |

### Budget premier mois (test + développement)
- Bases (Supabase, Vercel, Stripe, n8n) : **0€**
- APIs IA : **~10€** (Claude)
- Voice (Vapi + Twilio) : **~5€** (tests)
- Vidéo (HeyGen + ElevenLabs) : **~29€** (premier mois abonnement)
- **Total : ~44€**

### Budget mois suivant (production, 10 clients)
- APIs IA : **~50-100€**
- Vapi : **~20-50€** (appels entrants/sortants)
- HeyGen : **24€** (abonnement fixe)
- **Total : ~100-175€**
- **Revenu : 10 × 59€ (Pro) = 590€**
- **Marge nette : ~400€/mois dès 10 clients**
