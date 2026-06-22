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

#### Étape 3 : Déployer le webhook sur ta plateforme
Les routes API sont déjà créées :
- `POST /api/vapi/webhook` → reçoit les événements d'appel
- `POST /api/vapi/create-call` → lance un appel depuis la plateforme

Ajoute ces variables dans ton `.env.local` :
```bash
VAPI_API_KEY=ta_cle_vapi_trouvee_dans_settings
VAPI_ASSISTANT_ID=l_id_de_l_assistant_cree
ELEVENLABS_API_KEY=ta_cle_optionnelle
TWILIO_ACCOUNT_SID=ton_account_sid
TWILIO_AUTH_TOKEN=ton_auth_token
TWILIO_PHONE_NUMBER=+33...
NEXT_PUBLIC_APP_URL=https://ton-site.vercel.app
```

### Test
1. Va dans ton dashboard Vapi → **Playground**
2. Clique "Start call" ou appelle ton numéro Twilio
3. L'agent répond avec le prompt de l'agent téléphonique
4. Vérifie que les logs arrivent sur `ta-plateforme/api/vapi/webhook`

---

## 2. CRÉATEUR VIDÉO IA (HeyGen + Runway)

### Stack nécessaire

| Service | Rôle | Lien | Coût |
|---|---|---|---|
| **HeyGen** | Avatars IA parlants (vidéo avec visage qui parle) | [heygen.com](https://heygen.com) | 24$/mois (Creator) |
| **Runway** | Génération vidéo (scènes, animations sans avatar) | [runwayml.com](https://runwayml.com) | 15$/mois (Standard) |
| **ElevenLabs** | Voix off pour les vidéos | [elevenlabs.io](https://elevenlabs.io) | 5$/mois (Starter) |

### Architecture
```
Ta plateforme → API HeyGen → Génération avatar IA parlant
             → API Runway  → Génération scènes vidéo
             → ElevenLabs  → Doublage voix off multilingue
```

### Procédure HeyGen

#### Étape 1 : Créer un compte HeyGen
1. Va sur https://heygen.com → "Get Started"
2. Choisis le plan **Creator** (24$/mois)
3. Va dans **API** → "Create API Key"
4. Note la clé → `HEYGEN_API_KEY=ta_cle`

#### Étape 2 : Créer un avatar
1. Dans HeyGen → **Avatars → Instant Avatar**
   - Soit tu uploades une vidéo de toi (personnalisé)
   - Soit tu choisis un avatar prêt à l'emploi dans la galerie
2. Pour le multilingue, choisis un avatar qui supporte le français, anglais, arabe
3. Note le **Avatar ID**

### Connexion à la plateforme

Crée une route API pour générer des vidéos :

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="write_file">
<｜｜DSML｜｜parameter name="content" string="true">// /workspace/hermes-saas/platform/src/app/api/video/generate/route.ts
import { NextRequest, NextResponse } from 'next/server'

const HEYGEN_API_KEY=proces..._KEY || ''
const HEYGEN_API_URL = 'https://api.heygen.com/v2'

export async function POST(req: NextRequest) {
  if (!HEYGEN_API_KEY) {
    return NextResponse.json(
      { error: 'HeyGen API key not configured' },
      { status: 400 }
    )
  }

  const { script, avatarId, voiceId, language, title } = await req.json()

  try {
    // Étape 1: Créer la vidéo
    const createRes = await fetch(`${HEYGEN_API_URL}/video/generate`, {
      method: 'POST',
      headers: {
        'X-Api-Key': HEYGEN_API_KEY,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        caption: true,
        title: title || 'Vidéo Hermes SaaS',
        video_inputs: [
          {
            character: {
              type: 'avatar',
              avatar_id: avatarId || 'default',
              avatar_style: 'normal',
            },
            voice: {
              type: 'text',
              input_text: script,
              voice_id: voiceId || 'default',
              speed: 1.0,
            },
            background: {
              type: 'color',
              value: '#1a1a2e',
            },
          },
        ],
        dimension: {
          width: 1920,
          height: 1080,
        },
        aspect_ratio: '16:9',
        test: false,
      }),
    })

    const videoData = await createRes.json()
    const videoId = videoData.data?.video_id

    if (!videoId) {
      throw new Error('No video ID returned')
    }

    // Étape 2: La vidéo est en cours de génération
    // On retourne l'ID pour polling
    return NextResponse.json({
      success: true,
      videoId,
      status: 'generating',
      estimatedTime: 120, // secondes
    })
  } catch (error) {
    console.error('Video generation error:', error)
    return NextResponse.json(
      { error: "Erreur lors de la génération de la vidéo" },
      { status: 500 }
    )
  }
}

// GET /api/video/generate?videoId=xxx → vérifier le statut
export async function GET(req: NextRequest) {
  const videoId = req.nextUrl.searchParams.get('videoId')

  if (!videoId) {
    return NextResponse.json({ error: 'videoId required' }, { status: 400 })
  }

  try {
    const res = await fetch(
      `${HEYGEN_API_URL}/video/status?video_id=${videoId}`,
      {
        headers: { 'X-Api-Key': HEYGEN_API_KEY },
      }
    )
    const data = await res.json()

    return NextResponse.json({
      status: data.data?.status || 'unknown',
      videoUrl: data.data?.video_url || null,
      thumbnailUrl: data.data?.thumbnail_url || null,
    })
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to check video status' },
      { status: 500 }
    )
  }
}
