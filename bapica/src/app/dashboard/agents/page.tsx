import { Metadata } from 'next'
import Link from 'next/link'
import {
  Bot,
  Phone,
  FileText,
  Video,
  HeadphonesIcon,
  Building2,
  Search,
  FileCheck,
  Calculator,
  BarChart3,
  Users,
  Sparkles,
} from 'lucide-react'

export const metadata: Metadata = {
  title: 'Mes agents - Hermes SaaS',
}

const agentIcons: Record<string, React.ElementType> = {
  Bot,
  Phone,
  FileText,
  Video,
  HeadphonesIcon,
  Building2,
  Search,
  FileCheck,
  Calculator,
  Users,
  BarChart3,
}

// Liste complète des 11 agents
const agents = [
  { id: 'general', name: 'Agent Général', icon: 'Bot', desc: 'Assistant universel', plan: 'Starter', color: 'from-blue-500 to-blue-600' },
  { id: 'support', name: 'Support Client', icon: 'HeadphonesIcon', desc: 'Support 24/7', plan: 'Starter', color: 'from-emerald-500 to-emerald-600' },
  { id: 'content', name: 'Créateur de Contenu', icon: 'FileText', desc: 'SEO & réseaux sociaux', plan: 'Starter', color: 'from-violet-500 to-violet-600' },
  { id: 'prospector', name: 'Prospecteur Commercial', icon: 'Users', desc: 'Leads B2B', plan: 'Pro', color: 'from-orange-500 to-orange-600' },
  { id: 'closer', name: 'Closer Vocal', icon: 'Phone', desc: 'Vente par téléphone', plan: 'Pro', color: 'from-rose-500 to-rose-600' },
  { id: 'telephone', name: 'Agent Téléphonique', icon: 'Building2', desc: 'Standard virtuel', plan: 'Pro', color: 'from-cyan-500 to-cyan-600' },
  { id: 'accounting', name: 'Agent Comptabilité', icon: 'Calculator', desc: 'Factures & TVA', plan: 'Pro', color: 'from-amber-500 to-amber-600' },
  { id: 'video', name: 'Créateur Vidéo IA', icon: 'Video', desc: 'Vidéos & Reels', plan: 'Business', color: 'from-pink-500 to-pink-600' },
  { id: 'recruiter', name: 'Recruteur IA', icon: 'Search', desc: 'Recrutement automatisé', plan: 'Business', color: 'from-indigo-500 to-indigo-600' },
  { id: 'legal', name: 'Administratif & Juridique', icon: 'FileCheck', desc: 'Contrats & RGPD', plan: 'Business', color: 'from-slate-500 to-slate-600' },
  { id: 'analytics', name: 'Analytics & Reporting', icon: 'BarChart3', desc: 'Data & KPIs', plan: 'Business', color: 'from-teal-500 to-teal-600' },
]

const planColors: Record<string, string> = {
  Starter: 'bg-blue-500/10 text-blue-500',
  Pro: 'bg-orange-500/10 text-orange-500',
  Business: 'bg-purple-500/10 text-purple-500',
}

export default function AgentsPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Mes agents</h1>
        <p className="mt-1 text-muted-foreground">
          Sélectionnez un agent pour commencer à travailler.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {agents.map((agent) => {
          const Icon = agentIcons[agent.icon] || Bot
          return (
            <Link
              key={agent.id}
              href={`/dashboard/agents/${agent.id}`}
              className="group relative rounded-xl border border-border bg-card p-5 hover:border-primary/50 transition-all hover:shadow-lg hover:-translate-y-0.5"
            >
              <div className={`mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br ${agent.color} text-white shadow-lg`}>
                <Icon className="h-6 w-6" />
              </div>
              <h3 className="font-semibold group-hover:text-primary transition-colors">
                {agent.name}
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">{agent.desc}</p>
              <div className="mt-3 flex items-center justify-between">
                <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${planColors[agent.plan]}`}>
                  {agent.plan}
                </span>
                <Sparkles className="h-4 w-4 text-muted-foreground/30 group-hover:text-primary/50 transition-colors" />
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
