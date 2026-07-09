import type { MetadataRoute } from "next"
import AGENTS from "@/lib/agents"

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = "https://bapica.com"
  const today = new Date()

  const staticPages = [
    { url: baseUrl, lastModified: today, changeFrequency: "weekly" as const, priority: 1 },
    { url: `${baseUrl}/faq`, lastModified: today, changeFrequency: "weekly" as const, priority: 0.7 },
    { url: `${baseUrl}/a-propos`, lastModified: today, changeFrequency: "monthly" as const, priority: 0.5 },
    { url: `${baseUrl}/contact`, lastModified: today, changeFrequency: "monthly" as const, priority: 0.6 },
    { url: `${baseUrl}/affiliation`, lastModified: today, changeFrequency: "monthly" as const, priority: 0.6 },
    { url: `${baseUrl}/login`, lastModified: today, changeFrequency: "yearly" as const, priority: 0.3 },
    { url: `${baseUrl}/signup`, lastModified: today, changeFrequency: "monthly" as const, priority: 0.8 },
    { url: `${baseUrl}/forgot-password`, lastModified: today, changeFrequency: "yearly" as const, priority: 0.2 },
    { url: `${baseUrl}/essai-gratuit`, lastModified: today, changeFrequency: "monthly" as const, priority: 0.9 },
  ]

  const legalPages = [
    "cgv",
    "mentions-legales",
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
