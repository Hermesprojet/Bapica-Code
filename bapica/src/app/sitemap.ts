import type { MetadataRoute } from "next"
import AGENTS from "@/lib/agents"

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = "https://bapica.com"
  const today = new Date()

  const staticPages = [
    { url: baseUrl, lastModified: today, changeFrequency: "weekly" as const, priority: 1 },
    { url: `${baseUrl}/signup`, lastModified: today, changeFrequency: "monthly" as const, priority: 0.9 },
    { url: `${baseUrl}/faq`, lastModified: today, changeFrequency: "weekly" as const, priority: 0.7 },
    { url: `${baseUrl}/blog`, lastModified: today, changeFrequency: "weekly" as const, priority: 0.7 },
    { url: `${baseUrl}/blog/limova-vs-bapica`, lastModified: today, changeFrequency: "monthly" as const, priority: 0.7 },
    { url: `${baseUrl}/contact`, lastModified: today, changeFrequency: "monthly" as const, priority: 0.6 },
    { url: `${baseUrl}/affiliation`, lastModified: today, changeFrequency: "monthly" as const, priority: 0.6 },
    { url: `${baseUrl}/a-propos`, lastModified: today, changeFrequency: "monthly" as const, priority: 0.5 },
    { url: `${baseUrl}/login`, lastModified: today, changeFrequency: "yearly" as const, priority: 0.3 },
  ]

  const legalPages = [
    "cgv", "cgu", "privacy", "rgpd", "mentions-legales", "rgpd-exercer-droits"
  ].map((slug) => ({
    url: `${baseUrl}/legal/${slug}`,
    lastModified: today,
    changeFrequency: "monthly" as const,
    priority: 0.3,
  }))

  const agentPages = AGENTS.map((agent) => ({
    url: `${baseUrl}/agents/${agent.id}`,
    lastModified: today,
    changeFrequency: "monthly" as const,
    priority: 0.6,
  }))

  return [...staticPages, ...legalPages, ...agentPages]
}
