/**
 * Client Twenty CRM (self-hosted) — src/lib/twenty.ts
 *
 * Variables d'environnement attendues :
 *   TWENTY_API_URL   ex: https://crm.tondomaine.com
 *   TWENTY_API_KEY   clé générée dans Twenty > Settings > API & Webhooks
 */

import { createClient } from "@/lib/supabase"
import { type SupabaseClient } from "@supabase/supabase-js"

export interface TwentyCredentials {
  apiUrl: string
  apiKey: string
}

export async function getTwentyCredentials(
  userId: string
): Promise<TwentyCredentials | null> {
  const supabase = createClient() as SupabaseClient
  const { data, error } = await supabase
    .from("integrations")
    .select("api_url, api_key")
    .eq("user_id", userId)
    .eq("provider", "twenty")
    .single()

  if (error || !data) return null

  return {
    apiUrl: data.api_url,
    apiKey: data.api_key,
  }
}

async function twentyRequest<T = any>(
  creds: TwentyCredentials,
  query: string,
  variables?: Record<string, unknown>
): Promise<T> {
  const res = await fetch(`${creds.apiUrl.replace(/\/$/, "")}/graphql`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${creds.apiKey}`,
    },
    body: JSON.stringify({ query, variables }),
    cache: "no-store",
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Twenty API error (${res.status}): ${text}`)
  }

  const json = await res.json()
  if (json.errors) {
    throw new Error(`Twenty GraphQL error: ${JSON.stringify(json.errors)}`)
  }

  return json.data as T
}

/* Personnes */

export async function searchPeople(creds: TwentyCredentials, query: string) {
  return twentyRequest(creds,
    `query SearchPeople($filter: PersonFilterInput) {
      people(filter: $filter, first: 10) {
        edges {
          node {
            id
            name { firstName lastName }
            emails { primaryEmail }
            phones { primaryPhoneNumber }
            company { id name }
          }
        }
      }
    }`,
    { filter: { or: [
      { name: { firstName: { ilike: `%${query}%` } } },
      { name: { lastName: { ilike: `%${query}%` } } },
      { emails: { primaryEmail: { ilike: `%${query}%` } } },
    ] } }
  )
}

export async function createPerson(
  creds: TwentyCredentials,
  data: { firstName: string; lastName: string; email?: string; phone?: string; companyId?: string }
) {
  return twentyRequest(creds,
    `mutation CreatePerson($input: PersonCreateInput!) {
      createPerson(data: $input) { id name { firstName lastName } }
    }`,
    { input: {
      name: { firstName: data.firstName, lastName: data.lastName },
      emails: data.email ? { primaryEmail: data.email } : undefined,
      phones: data.phone ? { primaryPhoneNumber: data.phone } : undefined,
      companyId: data.companyId,
    } }
  )
}

export async function updatePerson(creds: TwentyCredentials, id: string, data: Record<string, unknown>) {
  return twentyRequest(creds,
    `mutation UpdatePerson($id: ID!, $input: PersonUpdateInput!) { updatePerson(id: $id, data: $input) { id } }`,
    { id, input: data }
  )
}

/* Entreprises */

export async function searchCompanies(creds: TwentyCredentials, query: string) {
  return twentyRequest(creds,
    `query SearchCompanies($filter: CompanyFilterInput) {
      companies(filter: $filter, first: 10) {
        edges { node { id name domainName { primaryLinkUrl } employees } }
      }
    }`,
    { filter: { name: { ilike: `%${query}%` } } }
  )
}

export async function createCompany(creds: TwentyCredentials, data: { name: string; domain?: string; employees?: number }) {
  return twentyRequest(creds,
    `mutation CreateCompany($input: CompanyCreateInput!) { createCompany(data: $input) { id name } }`,
    { input: { name: data.name, domainName: data.domain ? { primaryLinkUrl: data.domain } : undefined, employees: data.employees } }
  )
}

/* Opportunités */

export async function searchOpportunities(creds: TwentyCredentials, query: string) {
  return twentyRequest(creds,
    `query SearchOpportunities($filter: OpportunityFilterInput) {
      opportunities(filter: $filter, first: 10) {
        edges { node { id name amount { amountMicros currencyCode } stage closeDate company { id name } } }
      }
    }`,
    { filter: { name: { ilike: `%${query}%` } } }
  )
}

export async function createOpportunity(
  creds: TwentyCredentials,
  data: { name: string; amount?: number; stage?: string; companyId?: string; closeDate?: string }
) {
  return twentyRequest(creds,
    `mutation CreateOpportunity($input: OpportunityCreateInput!) { createOpportunity(data: $input) { id name stage } }`,
    { input: {
      name: data.name,
      amount: data.amount ? { amountMicros: data.amount * 1_000_000, currencyCode: "EUR" } : undefined,
      stage: data.stage ?? "NEW",
      companyId: data.companyId,
      closeDate: data.closeDate,
    } }
  )
}

export async function updateOpportunityStage(creds: TwentyCredentials, id: string, stage: string) {
  return twentyRequest(creds,
    `mutation UpdateOpportunityStage($id: ID!, $input: OpportunityUpdateInput!) { updateOpportunity(id: $id, data: $input) { id stage } }`,
    { id, input: { stage } }
  )
}
