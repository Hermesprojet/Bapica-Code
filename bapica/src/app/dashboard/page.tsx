import { Bot, Users, MessageSquare, TrendingUp } from 'lucide-react'

const cards = [
  {
    title: 'Agents actifs',
    value: '3',
    desc: 'sur 11 disponibles',
    icon: Bot,
    change: '+2 ce mois',
    positive: true,
  },
  {
    title: 'Conversations',
    value: '127',
    desc: 'ce mois-ci',
    icon: MessageSquare,
    change: '+23%',
    positive: true,
  },
  {
    title: 'Leads générés',
    value: '45',
    desc: 'par l\'agent prospecteur',
    icon: Users,
    change: '+12 cette semaine',
    positive: true,
  },
  {
    title: 'Crédits utilisés',
    value: '34%',
    desc: 'du forfait mensuel',
    icon: TrendingUp,
    change: '66% restants',
    positive: true,
  },
]

export default function DashboardPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Tableau de bord</h1>
        <p className="mt-1 text-muted-foreground">
          Bienvenue sur votre espace Hermes SaaS.
        </p>
      </div>

      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => {
          const Icon = card.icon
          return (
            <div
              key={card.title}
              className="rounded-xl border border-border bg-card p-6"
            >
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="h-5 w-5" />
                </div>
                <span className="text-xs font-medium text-green-500">
                  {card.change}
                </span>
              </div>
              <div className="mt-4">
                <p className="text-2xl font-bold">{card.value}</p>
                <p className="text-sm text-muted-foreground">{card.title}</p>
                <p className="mt-1 text-xs text-muted-foreground">{card.desc}</p>
              </div>
            </div>
          )
        })}
      </div>

      {/* Quick actions */}
      <div className="mt-12">
        <h2 className="mb-4 text-lg font-semibold">Actions rapides</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <a
            href="/dashboard/agents"
            className="rounded-xl border border-border bg-card p-6 hover:border-primary/50 transition-all hover:shadow-md"
          >
            <h3 className="font-semibold">🤖 Parler à un agent</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Discutez avec vos assistants IA spécialisés.
            </p>
          </a>
          <a
            href="/dashboard/billing"
            className="rounded-xl border border-border bg-card p-6 hover:border-primary/50 transition-all hover:shadow-md"
          >
            <h3 className="font-semibold">📊 Gérer mon abonnement</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Voir votre forfait, changer de formule.
            </p>
          </a>
          <a
            href="/dashboard/settings"
            className="rounded-xl border border-border bg-card p-6 hover:border-primary/50 transition-all hover:shadow-md"
          >
            <h3 className="font-semibold">⚙️ Configuration</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              API keys, préférences, profil.
            </p>
          </a>
        </div>
      </div>
    </div>
  )
}
