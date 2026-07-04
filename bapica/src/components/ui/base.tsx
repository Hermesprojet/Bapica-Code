// Composants UI de base pour Bapica

// Skeleton pour le chargement
export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-white/5 ${className}`}
      style={{ animationDuration: '1.5s' }}
    />
  )
}

export function CardSkeleton() {
  return (
    <div className="card-elevated p-6 space-y-4">
      <Skeleton className="h-10 w-10 rounded-lg" />
      <Skeleton className="h-5 w-32" />
      <Skeleton className="h-4 w-48" />
    </div>
  )
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-8">
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {[1,2,3,4].map(i => <CardSkeleton key={i} />)}
      </div>
      <div className="space-y-4">
        <Skeleton className="h-6 w-40" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1,2,3].map(i => <CardSkeleton key={i} />)}
        </div>
      </div>
    </div>
  )
}

// Empty state
export function EmptyState({
  icon = '📭',
  title = 'Aucune donnée',
  description = 'Commencez à utiliser vos agents pour voir les résultats ici.',
  action,
}: {
  icon?: string
  title?: string
  description?: string
  action?: { label: string; href: string }
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <span className="text-4xl mb-4">{icon}</span>
      <h3 className="text-lg font-semibold text-foreground">{title}</h3>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">{description}</p>
      {action && (
        <a
          href={action.href}
          className="btn-ghost mt-6 inline-flex items-center gap-2 px-4 py-2 text-sm"
        >
          {action.label}
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
        </a>
      )}
    </div>
  )
}
