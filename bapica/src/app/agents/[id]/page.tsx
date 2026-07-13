import { notFound } from 'next/navigation'
import AGENTS from '@/lib/agents'
import AgentChatClient from './agent-chat-client'

export default function AgentPage({ params }: { params: { id: string } }) {
  // Server Component : notFound() ici renvoie un vrai statut HTTP 404
  // pour un id inconnu, avant tout streaming du HTML.
  const agent = AGENTS.find(a => a.id === params.id)
  if (!agent) {
    notFound()
  }

  return <AgentChatClient agent={agent} />
}
