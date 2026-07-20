// Déclaration minimale pour imapflow (le paquet n'expose pas de types résolus par TS).
declare module 'imapflow' {
  export class ImapFlow {
    constructor(options: Record<string, unknown>)
    mailbox: { exists: number } | boolean
    connect(): Promise<void>
    logout(): Promise<void>
    getMailboxLock(name: string): Promise<{ release(): void }>
    fetch(range: string, query: Record<string, unknown>): AsyncIterable<{ envelope?: any }>
    mailboxOpen(name: string): Promise<unknown>
  }
}
