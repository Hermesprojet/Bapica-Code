// Génération et retouche d'images via OpenAI Images (gpt-image-1).
// Un seul fournisseur pour CRÉER une image (texte → image) et la MODIFIER (image + consigne).
// Clé : OPENAI_API_KEY (déjà utilisée pour les embeddings/RAG). Écrit à l'aveugle (non testable
// en sandbox : pas de clé + réseau bloqué) — les erreurs OpenAI sont remontées brutes.

const OPENAI_IMAGES = 'https://api.openai.com/v1/images'

export type ImageSize = '1024x1024' | '1024x1536' | '1536x1024' | 'auto'

function keyOrThrow(): string {
  const k = process.env.OPENAI_API_KEY
  if (!k) throw new Error('IMAGE_NOT_CONFIGURED')
  return k
}

/** Texte → image. Renvoie le PNG encodé en base64 (sans préfixe data:). */
export async function generateImage(prompt: string, size: ImageSize = '1024x1024'): Promise<string> {
  const key = keyOrThrow()
  const res = await fetch(`${OPENAI_IMAGES}/generations`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: 'gpt-image-1', prompt: prompt.slice(0, 4000), size, n: 1 }),
    signal: AbortSignal.timeout(120000),
  })
  const data = await res.json().catch(() => ({}))
  const b64 = data?.data?.[0]?.b64_json
  if (!res.ok || !b64) throw new Error(`OpenAI (image) : ${data?.error?.message || JSON.stringify(data).slice(0, 300)}`)
  return b64
}

/** Image existante + consigne → image modifiée. Renvoie le PNG en base64 (sans préfixe data:). */
export async function editImage(image: Blob, prompt: string, size: ImageSize = '1024x1024'): Promise<string> {
  const key = keyOrThrow()
  const form = new FormData()
  form.append('model', 'gpt-image-1')
  form.append('image', image, 'image.png')
  form.append('prompt', prompt.slice(0, 4000))
  if (size !== 'auto') form.append('size', size)
  const res = await fetch(`${OPENAI_IMAGES}/edits`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${key}` },
    body: form,
    signal: AbortSignal.timeout(120000),
  })
  const data = await res.json().catch(() => ({}))
  const b64 = data?.data?.[0]?.b64_json
  if (!res.ok || !b64) throw new Error(`OpenAI (retouche image) : ${data?.error?.message || JSON.stringify(data).slice(0, 300)}`)
  return b64
}
