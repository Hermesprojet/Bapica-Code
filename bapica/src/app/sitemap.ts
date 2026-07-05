import type { MetadataRoute } from "next"
import AGENTS from "@/lib/agents"

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = "https://bapica.com"

  // Use a realistic last modified date (update this when content changes)
  const lastMod = new Date("2026-07-05")

  const staticPages = [
    { url: baseUrl, lastModified: lastMod, changeFrequency: "weekly" as const, priority: 1 },
    { url: `${baseUrl}/faq`, lastModified: lastMod, changeFrequency: "weekly" as const, priority: 0.6 },
    { url: `${baseUrl}/a-propos`, lastModified: lastMod, changeFrequency: "monthly" as const, priority: 0.5 },
    { url: `${baseUrl}/blog`, lastModified: lastMod, changeFrequency: "weekly" as const, priority: 0.7 },
    { url: `${baseUrl}/contact`, lastModified: lastMod, changeFrequency: "monthly" as const, priority: 0.6 },
    { url: `${baseUrl}/login`, lastModified: lastMod, changeFrequency: "yearly" as const, priority: 0.3 },
    { url: `${baseUrl}/signup`, lastModified: lastMod, changeFrequency: "monthly" as const, priority: 0.8 },
  ]

  const legalPages = [
    "cgv",
    "cgu",
    "privacy",
    "rgpd",
    "mentions-legales",
  ].map((slug) => ({
    url: `${baseUrl}/legal/${slug}`,
    lastModified: lastMod,
    changeFrequency: "monthly" as const,
    priority: 0.2,
  }))

  const agentPages = AGENTS.map((agent) => ({
    url: `${baseUrl}/agents/${agent.id}`,
    lastModified: lastMod,
    changeFrequency: "monthly" as const,
    priority: 0.6,
  }))

  return [...staticPages, ...legalPages, ...agentPages]
}
