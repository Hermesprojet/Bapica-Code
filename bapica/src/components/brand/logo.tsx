import { cn } from '@/lib/utils'

interface LogoProps {
  size?: number
  showWordmark?: boolean
  className?: string
  wordmarkClassName?: string
}

/**
 * Logo de la marque Bapica : un monogramme « B » sur une tuile dégradée,
 * accompagné du wordmark « Bapica ». Rendu 100 % SVG (net, léger, sans asset).
 */
export function Logo({
  size = 32,
  showWordmark = true,
  className,
  wordmarkClassName,
}: LogoProps) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 40 40"
        role="img"
        aria-label="Bapica"
        className="shrink-0"
      >
        <defs>
          <linearGradient id="bapica-logo-grad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#3b82f6" />
            <stop offset="50%" stopColor="#6366f1" />
            <stop offset="100%" stopColor="#8b5cf6" />
          </linearGradient>
        </defs>
        <rect width="40" height="40" rx="11" fill="url(#bapica-logo-grad)" />
        {/* Monogramme « B » */}
        <path
          d="M14 10 V30 M14 10 H22 a5 5 0 0 1 0 10 H14 M14 20 H23 a5.5 5.5 0 0 1 0 10 H14"
          fill="none"
          stroke="#ffffff"
          strokeWidth="3.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Étincelle « IA » */}
        <circle cx="30" cy="11" r="2.4" fill="#ffffff" />
      </svg>
      {showWordmark && (
        <span className={cn('font-bold tracking-tight', wordmarkClassName ?? 'text-lg')}>
          Bapica
        </span>
      )}
    </span>
  )
}

export default Logo
