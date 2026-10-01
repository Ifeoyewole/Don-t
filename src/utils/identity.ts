export function createId(): string {
  return crypto.randomUUID()
}

export function createTimestamp(): string {
  return new Date().toISOString()
}
