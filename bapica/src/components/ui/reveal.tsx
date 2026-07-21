'use client'

import { useEffect, useRef, useState, type ReactNode } from 'react'

interface RevealProps {
  children: ReactNode
  className?: string
  /** Décalage (ms) pour un effet en cascade quand plusieurs Reveal sont côte à côte. */
  delay?: number
}

/**
 * Révélation au défilement (IntersectionObserver), façon Emil Kowalski :
 * fondu + léger slide-up en ease-out, une seule fois.
 *
 * Progressive enhancement : la classe `.reveal-on-scroll` n'est masquée par CSS
 * QUE lorsque `<html class="js-reveal">` est présent (posé par un script dans le
 * <head>). Sans JS, le contenu reste visible — robots et lecteurs inclus.
 * Respecte aussi `prefers-reduced-motion`.
 */
export function Reveal({ children, className = '', delay = 0 }: RevealProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      setVisible(true)
      return
    }
    const obs = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setVisible(true)
            obs.disconnect()
            break
          }
        }
      },
      { threshold: 0.1, rootMargin: '0px 0px -10% 0px' },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  return (
    <div
      ref={ref}
      className={`reveal-on-scroll ${visible ? 'is-visible' : ''} ${className}`}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </div>
  )
}
