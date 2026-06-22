# Intégration Vapi — Agent Vocal & Téléphonique

## Qu'est-ce que Vapi ?
Vapi est une plateforme qui permet de créer des **agents vocaux IA** capables de passer et recevoir des appels téléphoniques. Ils parlent naturellement, comprennent le contexte, et s'intègrent à vos outils.

## Comptes nécessaires

| Service | Rôle | Coût |
|---|---|---|
| **Vapi** | Moteur vocal IA | 0.07€/min d'appel |
| **Twilio** | Numéro de téléphone + infrastructure téléphonique | ~1€/mois par numéro + 0.014€/min |
| **ElevenLabs** | Voix naturelle (optionnel, sinon Vapi a ses voix par défaut) | 5$/mois (Starter) |

## Étapes de connexion

### 1. Créer un compte Vapi
1. Va sur https://vapi.ai → Sign up
2. Crée un "Assistant" → choisis un nom (ex: "Standard téléphonique")
3. Configure :
   - **System Prompt** → copie le contenu du fichier `agents/prompts/agent-06-agent-telephonique.md` ou `agent-02-closer-vocal.md`
   - **Modèle** → Claude Sonnet ou GPT-4o-mini (moins cher pour la voix)
   - **Voix** → Choisis "ElevenLabs Multilingual v2" pour le français/anglais/arabe
   - **Langue** → "Auto-détection"
4. Note le **Assistant ID** (ex: `abc-123`)

### 2. Connecter un numéro Twilio
1. Va sur https://twilio.com → crée un compte
2. Achète un numéro de téléphone : **Console → Phone Numbers → Buy a number**
   - Choisis un numéro français (+33...) ou ce que tu veux
   - Active les capacités "Voice"
3. Dans Vapi : **Settings → Phone Numbers → Add Number**
   - Colle le numéro Twilio
   - Colle le Account SID et Auth Token de Twilio

### 3. Connexion à ta plateforme Next.js

Ajoute cette route API :

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="write_file">
<｜｜DSML｜｜parameter name="content" string="true">// /workspace/hermes-saas/platform/src/app/api/vapi/webhook/route.ts
import { NextRequest, NextResponse } from 'next/server'

// Vapi envoie un webhook à chaque événement d'appel
export async function POST(req: NextRequest) {
  const body = await req.json()

  // Type d'événement Vapi
  const { type, call, assistantId, artifact } = body

  switch (type) {
    case 'call.started':
      // Un appel commence
      console.log(`Appel entrant de ${call.fromNumber}`)
      break

    case 'call.ended':
      // Appel terminé → sauvegarder le résumé
      console.log('Résumé appel:', artifact?.messages || [])
      // TODO: Sauvegarder dans Supabase
      break

    case 'call.scheduled':
      // Rappel programmé
      break
  }

  return NextResponse.json({ received: true })
}

// GET = vérifier que le webhook est en vie
export async function GET() {
  return NextResponse.json({ status: 'ok', service: 'vapi-webhook' })
}
