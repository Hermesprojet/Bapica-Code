import type { AgentConfig, AgentAvatar as AgentAvatarData } from '@/lib/agents'

interface AgentAvatarProps {
  agent: Pick<AgentConfig, 'id' | 'avatar'>
  size?: number
  className?: string
}

const EYE = '#3a3a3a'

function BackHair({ data }: { data: AgentAvatarData }) {
  // Mèches latérales visibles uniquement pour les cheveux longs
  if (data.hair !== 'long') return null
  return (
    <>
      <rect x="27" y="44" width="6" height="24" rx="3" fill={data.hairColor} />
      <rect x="67" y="44" width="6" height="24" rx="3" fill={data.hairColor} />
    </>
  )
}

function TopHair({ data }: { data: AgentAvatarData }) {
  const c = data.hairColor
  switch (data.hair) {
    case 'bald':
      return null
    case 'buzz':
      return <path d="M30 45 Q30 28 50 28 Q70 28 70 45 Q66 39 50 38 Q34 39 30 45 Z" fill={c} opacity={0.85} />
    case 'short':
      return <path d="M29 47 Q28 25 50 25 Q72 25 71 47 Q66 36 50 35 Q34 36 29 47 Z" fill={c} />
    case 'long':
      return <path d="M28 50 Q26 24 50 24 Q74 24 72 50 Q66 35 50 34 Q34 35 28 50 Z" fill={c} />
    case 'bun':
      return (
        <>
          <circle cx="50" cy="21" r="7" fill={c} />
          <path d="M30 46 Q30 26 50 26 Q70 26 70 46 Q66 37 50 36 Q34 37 30 46 Z" fill={c} />
        </>
      )
    case 'curly':
      return (
        <>
          {[32, 40, 50, 60, 68].map((cx, i) => (
            <circle key={i} cx={cx} cy={i % 2 === 0 ? 30 : 27} r="8" fill={c} />
          ))}
          <path d="M30 46 Q30 30 50 30 Q70 30 70 46 Q66 38 50 37 Q34 38 30 46 Z" fill={c} />
        </>
      )
    default:
      return null
  }
}

function Accessory({ data }: { data: AgentAvatarData }) {
  switch (data.accessory) {
    case 'glasses':
      return (
        <g stroke={EYE} strokeWidth="1.8" fill="none">
          <circle cx="43" cy="47" r="6" />
          <circle cx="57" cy="47" r="6" />
          <path d="M49 47 H51" strokeLinecap="round" />
          <path d="M37 46 L33 45" strokeLinecap="round" />
          <path d="M63 46 L67 45" strokeLinecap="round" />
        </g>
      )
    case 'headset':
      return (
        <g fill="#2b2b2b">
          <path d="M28 47 Q28 22 50 22 Q72 22 72 47" stroke="#2b2b2b" strokeWidth="3.5" fill="none" />
          <rect x="24" y="45" width="8" height="13" rx="3" />
          <rect x="68" y="45" width="8" height="13" rx="3" />
          <path d="M68 57 Q60 64 54 61" stroke="#2b2b2b" strokeWidth="2.6" fill="none" strokeLinecap="round" />
          <circle cx="53" cy="60.5" r="2.6" />
        </g>
      )
    case 'cap':
      return (
        <g fill="#2b2b2b">
          <path d="M29 41 Q31 25 50 25 Q69 25 71 41 Z" />
          <path d="M29 41 H20 Q17 41 18 44 Q30 43 32 41 Z" />
        </g>
      )
    default:
      return null
  }
}

/**
 * Avatar illustré (SVG) unique pour chaque agent.
 * Composant pur (sans état) : compatible Server Components.
 */
export function AgentAvatar({ agent, size = 48, className }: AgentAvatarProps) {
  const data = agent.avatar
  const bgId = `bapica-avatar-bg-${agent.id}`
  const clipId = `bapica-avatar-clip-${agent.id}`

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      className={className}
      role="img"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={bgId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={data.from} />
          <stop offset="100%" stopColor={data.to} />
        </linearGradient>
        <clipPath id={clipId}>
          <circle cx="50" cy="50" r="50" />
        </clipPath>
      </defs>

      <circle cx="50" cy="50" r="50" fill={`url(#${bgId})`} />

      <g clipPath={`url(#${clipId})`}>
        {/* Épaules / vêtement */}
        <path d="M20 100 Q20 77 50 77 Q80 77 80 100 Z" fill="rgba(255,255,255,0.22)" />
        {/* Mèches arrière */}
        <BackHair data={data} />
        {/* Cou */}
        <rect x="44" y="60" width="12" height="16" rx="6" fill={data.skin} />
        {/* Oreilles */}
        <circle cx="30" cy="47" r="4" fill={data.skin} />
        <circle cx="70" cy="47" r="4" fill={data.skin} />
        {/* Tête */}
        <circle cx="50" cy="47" r="20" fill={data.skin} />
        {/* Cheveux du dessus */}
        <TopHair data={data} />
        {/* Visage */}
        <circle cx="43" cy="47" r="2.6" fill={EYE} />
        <circle cx="57" cy="47" r="2.6" fill={EYE} />
        <path d="M43 55 Q50 61 57 55" stroke={EYE} strokeWidth="2" fill="none" strokeLinecap="round" />
        {/* Accessoire (lunettes, casque...) */}
        <Accessory data={data} />
      </g>
    </svg>
  )
}

export default AgentAvatar
