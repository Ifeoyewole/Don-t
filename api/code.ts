import type { IncomingMessage, ServerResponse } from 'node:http'

/** Retired operations endpoint: never forwards cloud or GitHub commands. */
export default function handler(_req: IncomingMessage, res: ServerResponse) {
  res.writeHead(410, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' })
  res.end(JSON.stringify({ error: 'The operations console has been retired. Use the existing inspection workflow.' }))
}
