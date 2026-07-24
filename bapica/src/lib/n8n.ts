// Intégration N8N — délègue le RÉPÉTABLE à N8N. À la validation d'une automatisation,
// on crée dans N8N un workflow planifié (Schedule Trigger → HTTP Request qui rappelle
// Bapica sur /api/automations/run avec l'id + le secret de l'automatisation).
//
// ÉCRIT « à l'aveugle » : l'API N8N varie selon la version (le contrat des nœuds
// Schedule/HTTP peut demander un petit ajustement au 1er test réel). Dégrade proprement :
// si N8N n'est pas configuré, l'automatisation reste enregistrée mais non planifiée.

const HEADER = 'X-N8N-API-KEY'

export function n8nConfigured(): boolean {
  return !!(process.env.N8N_URL && process.env.N8N_API_KEY)
}

function apiBase(): string {
  return (process.env.N8N_URL || '').replace(/\/$/, '')
}

async function n8n(path: string, init?: RequestInit): Promise<{ ok: boolean; status: number; data: any }> {
  const res = await fetch(`${apiBase()}/api/v1${path}`, {
    ...init,
    headers: { [HEADER]: process.env.N8N_API_KEY || '', 'Content-Type': 'application/json', Accept: 'application/json', ...(init?.headers || {}) },
    signal: AbortSignal.timeout(15000),
  })
  const data = await res.json().catch(() => ({}))
  return { ok: res.ok, status: res.status, data }
}

/**
 * Crée et active un workflow planifié qui appelle `runUrl` (POST { automationId, secret })
 * selon le cron fourni. Renvoie l'id du workflow N8N.
 */
export async function createScheduledWorkflow(opts: {
  name: string
  cron: string
  runUrl: string
  automationId: string
  secret: string
}): Promise<{ ok: boolean; workflowId?: string; error?: string }> {
  if (!n8nConfigured()) return { ok: false, error: 'not-configured' }

  const workflow = {
    name: `Bapica — ${opts.name}`.slice(0, 120),
    nodes: [
      {
        parameters: { rule: { interval: [{ field: 'cronExpression', expression: opts.cron }] } },
        id: 'schedule',
        name: 'Planification',
        type: 'n8n-nodes-base.scheduleTrigger',
        typeVersion: 1.1,
        position: [260, 300],
      },
      {
        parameters: {
          method: 'POST',
          url: opts.runUrl,
          sendBody: true,
          specifyBody: 'json',
          jsonBody: JSON.stringify({ automationId: opts.automationId, secret: opts.secret }),
          options: {},
        },
        id: 'call',
        name: 'Exécuter Bapica',
        type: 'n8n-nodes-base.httpRequest',
        typeVersion: 4.2,
        position: [520, 300],
      },
    ],
    connections: { Planification: { main: [[{ node: 'Exécuter Bapica', type: 'main', index: 0 }]] } },
    settings: { executionOrder: 'v1' },
  }

  const created = await n8n('/workflows', { method: 'POST', body: JSON.stringify(workflow) })
  const workflowId = created.data?.id || created.data?.data?.id
  if (!created.ok || !workflowId) return { ok: false, error: `N8N (création) : ${created.data?.message || `HTTP ${created.status}`}` }

  // Activation (endpoint dédié selon les versions ; on tolère l'échec avec message).
  const activated = await n8n(`/workflows/${workflowId}/activate`, { method: 'POST' })
  if (!activated.ok) return { ok: true, workflowId, error: `Créé mais non activé : ${activated.data?.message || `HTTP ${activated.status}`}` }
  return { ok: true, workflowId: String(workflowId) }
}

export async function setWorkflowActive(workflowId: string, active: boolean): Promise<boolean> {
  if (!n8nConfigured()) return false
  const r = await n8n(`/workflows/${workflowId}/${active ? 'activate' : 'deactivate'}`, { method: 'POST' })
  return r.ok
}

export async function deleteWorkflow(workflowId: string): Promise<boolean> {
  if (!n8nConfigured()) return false
  const r = await n8n(`/workflows/${workflowId}`, { method: 'DELETE' })
  return r.ok
}
