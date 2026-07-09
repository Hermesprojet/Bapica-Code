/**
 * Tools Twenty CRM pour Anthropic tool_use
 * Permet aux agents Bapica d'interagir avec le CRM
 */

export const twentyTools = [
  {
    name: "search_contacts",
    description: "Recherche des contacts dans le CRM Twenty par nom ou email.",
    input_schema: {
      type: "object",
      properties: { query: { type: "string", description: "Nom, prénom ou email" } },
      required: ["query"],
    },
  },
  {
    name: "create_contact",
    description: "Crée une nouvelle fiche contact dans le CRM Twenty.",
    input_schema: {
      type: "object",
      properties: {
        firstName: { type: "string" },
        lastName: { type: "string" },
        email: { type: "string" },
        phone: { type: "string" },
        companyId: { type: "string" },
      },
      required: ["firstName", "lastName"],
    },
  },
  {
    name: "search_companies",
    description: "Recherche des entreprises dans le CRM Twenty.",
    input_schema: {
      type: "object",
      properties: { query: { type: "string" } },
      required: ["query"],
    },
  },
  {
    name: "create_company",
    description: "Crée une entreprise dans le CRM Twenty.",
    input_schema: {
      type: "object",
      properties: { name: { type: "string" }, domain: { type: "string" }, employees: { type: "number" } },
      required: ["name"],
    },
  },
  {
    name: "search_opportunities",
    description: "Recherche des opportunités dans le CRM Twenty.",
    input_schema: {
      type: "object",
      properties: { query: { type: "string" } },
      required: ["query"],
    },
  },
  {
    name: "create_opportunity",
    description: "Crée une opportunité commerciale dans le CRM Twenty.",
    input_schema: {
      type: "object",
      properties: {
        name: { type: "string" },
        amount: { type: "number" },
        stage: { type: "string", description: "NEW, SCREENING, MEETING, PROPOSAL, WON, LOST" },
        companyId: { type: "string" },
        closeDate: { type: "string" },
      },
      required: ["name"],
    },
  },
  {
    name: "update_opportunity_stage",
    description: "Met à jour le stage d'une opportunité CRM.",
    input_schema: {
      type: "object",
      properties: { opportunityId: { type: "string" }, stage: { type: "string" } },
      required: ["opportunityId", "stage"],
    },
  },
] as const

export const TWENTY_TOOL_NAMES = twentyTools.map((t) => t.name)
