import type { IncomingMessage, ServerResponse } from 'node:http'

/** JointInspect has no user-facing sign-in flow. */
export default function handler(_req: IncomingMessage, res: ServerResponse) {
  res.writeHead(410, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' })
  res.end(JSON.stringify({ error: 'User sign-in has been retired. Use the inspection workflow.' }))
}
