/**
 * Structured data (JSON-LD) for SEO.
 *
 * Schemas implemented:
 * - Organization: company identity for Google Knowledge Graph
 * - WebSite: site info + Sitelinks Searchbox
 * - FAQPage: FAQ rich results (used on /faq)
 * - BreadcrumbList: navigation breadcrumbs
 */

export interface OrganizationSchema {
  "@context": "https://schema.org"
  "@type": "Organization"
  name: string
  url: string
  logo: string
  description: string
  sameAs: string[]
  contactPoint?: {
    "@type": "ContactPoint"
    contactType: string
    availableLanguage: string | string[]
  }
}

export function getOrganizationSchema(): OrganizationSchema {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Bapica",
    url: "https://bapica.com",
    logo: "https://bapica.com/og-image.png",
    description:
      "Plateforme multi-agents IA pour PME et indépendants. Prospection, support, contenu, voix, recrutement, comptabilité et plus encore.",
    sameAs: [
      "https://twitter.com/bapica",
      "https://www.linkedin.com/company/bapica",
    ],
    contactPoint: {
      "@type": "ContactPoint",
      contactType: "customer support",
      availableLanguage: "French",
    },
  }
}

export interface WebSiteSchema {
  "@context": "https://schema.org"
  "@type": "WebSite"
  name: string
  url: string
  description: string
  inLanguage: string
  potentialAction?: {
    "@type": "SearchAction"
    target: {
      "@type": "EntryPoint"
      urlTemplate: string
    }
    "query-input": string
  }
}

export function getWebSiteSchema(): WebSiteSchema {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Bapica",
    url: "https://bapica.com",
    description:
      "Plateforme multi-agents IA pour PME et indépendants. Prospection, support, contenu, voix, recrutement, comptabilité et plus encore.",
    inLanguage: "fr",
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate: "https://bapica.com/search?q={search_term_string}",
      },
      "query-input": "required name=search_term_string",
    },
  }
}

export interface FAQSchema {
  "@context": "https://schema.org"
  "@type": "FAQPage"
  mainEntity: {
    "@type": "Question"
    name: string
    acceptedAnswer: {
      "@type": "Answer"
      text: string
    }
  }[]
}

export function getFAQSchema(): FAQSchema {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: [
      {
        "@type": "Question",
        name: "C'est quoi Bapica ?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Bapica est une plateforme qui vous donne accès à une équipe d'agents IA spécialisés pour votre entreprise : prospection, support client, contenu, voix, recrutement, comptabilité et plus. Les agents comprennent votre métier et exécutent vos tâches 24h/24.",
        },
      },
      {
        "@type": "Question",
        name: "Comment fonctionne l'essai gratuit ?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "L'essai gratuit vous donne accès à tous les agents Bapica pendant 15 jours, sans engagement et sans carte bancaire. Vous pouvez tester toutes les fonctionnalités et découvrir les agents adaptés à votre activité.",
        },
      },
      {
        "@type": "Question",
        name: "Quels sont les tarifs de Bapica ?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Bapica propose deux formules : Essentiel à 49€/mois avec 4 agents (Général, Support, Contenu, Téléphonique) et Pro à 79€/mois avec 13 agents + appels téléphoniques (0,20€/min) + analytics + onboarding personnalisé.",
        },
      },
      {
        "@type": "Question",
        name: "Mes données sont-elles sécurisées ?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Oui. Bapica est hébergé en Europe (Vercel, datacenter Frankfurt), toutes les données sont chiffrées, et nous sommes conformes RGPD. Vos données vous appartiennent et ne sont jamais utilisées pour entraîner des modèles tiers.",
        },
      },
      {
        "@type": "Question",
        name: "Puis-je annuler à tout moment ?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Oui, vous pouvez résilier votre abonnement à tout moment depuis votre espace client. Il n'y a aucun engagement de durée, et vous continuez à bénéficier du service jusqu'à la fin de la période facturée.",
        },
      },
      {
        "@type": "Question",
        name: "Dans quelles langues les agents sont-ils disponibles ?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Les agents Bapica détectent automatiquement la langue et répondent dans la même langue. Plus de 140 langues sont supportées, dont le français, l'anglais, l'espagnol, l'allemand, l'italien et bien d'autres.",
        },
      },
    ],
  }
}

export interface BreadcrumbSchema {
  "@context": "https://schema.org"
  "@type": "BreadcrumbList"
  itemListElement: {
    "@type": "ListItem"
    position: number
    name: string
    item: string
  }[]
}

export function getBreadcrumbSchema(
  items: { name: string; url: string }[]
): BreadcrumbSchema {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, i) => ({
      "@type": "ListItem" as const,
      position: i + 1,
      name: item.name,
      item: item.url,
    })),
  }
}

/**
 * Render a JSON-LD script tag for Next.js.
 * Place inside <head> via layout or page-level script injection.
 */
export function JsonLdScript({ data }: { data: Record<string, unknown> }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  )
}
