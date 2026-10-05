import type { IncomingMessage, ServerResponse } from 'node:http'

export default function handler(_req: IncomingMessage, res: ServerResponse) {
  const payload = JSON.stringify({ status: 'ok', service: 'joint-inspection-gateway' })
  res.writeHead(200, {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(payload),
    'Cache-Control': 'no-store, max-age=0',
  })
  res.end(payload)
}
