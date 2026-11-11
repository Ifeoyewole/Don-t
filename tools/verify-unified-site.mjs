/** Existing frontend -> actual protected gateway -> FastAPI -> saved real artifact.
 * No provider calls or models. Required input is a private real-run frame dir.
 */
import { createServer } from 'vite'
import { chromium } from 'playwright'
import { spawn, execFileSync } from 'node:child_process'
import fs from 'node:fs/promises'
import path from 'node:path'

const root = process.env.JOINTINSPECT_REPLAY_DIR
if (!root) throw Error('JOINTINSPECT_REPLAY_DIR is required; no synthetic fallback')
const output = process.env.JOINTINSPECT_VERIFY_OUTPUT || '/tmp/jointinspect-web-verification'
await fs.mkdir(output, { recursive: true })
execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', path.join(output,'test-key.pem'), '-out', path.join(output,'test-cert.pem'), '-subj', '/CN=localhost', '-days', '1'], {stdio:'ignore'})
Object.assign(process.env, { UNIFIED_ENGINEERING_PREVIEW_ENABLED: 'true', UNIFIED_PREVIEW_URL: 'https://unified-preview-fixture.a.run.app',
  UNIFIED_PREVIEW_MODE: 'PREVIEW', DEV_CLOUD_RUN_ID_TOKEN: 'synthetic-local-replay-token' })
const python = process.env.JOINTINSPECT_TEST_PYTHON || 'python'
const child = spawn(python, ['-m', 'uvicorn', 'tools.replay_unified_api:app', '--host', '127.0.0.1', '--port', '8000'], {
  env: { ...process.env, JOINTINSPECT_SEWER_FUSION_ENABLED: 'true', JOINTINSPECT_PHASE1_VERTEX_ENABLED: 'true',
    JOINTINSPECT_PREVIEW_TOKEN: 'synthetic-local-replay-token', OFFLINE_BENCHMARK_HARNESS: '1' }, stdio: ['ignore', 'pipe', 'pipe'] })
let log = '';child.stdout.on('data', b => {log += b});child.stderr.on('data', b => {log += b})
const nativeFetch = globalThis.fetch
globalThis.fetch = (input, options) => {
  const url = String(input)
  return nativeFetch(url.startsWith(process.env.UNIFIED_PREVIEW_URL) ? url.replace(process.env.UNIFIED_PREVIEW_URL, 'http://127.0.0.1:8000') : input, options)
}
let browser, vite, page
try {
  for (let i = 0; i < 50; i++) {
    try { if ((await nativeFetch('http://127.0.0.1:8000/health')).ok) break } catch {}
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  vite = await createServer({ server: { host: '127.0.0.1', port: 5173, strictPort: true, https: {key: await fs.readFile(path.join(output,'test-key.pem')), cert: await fs.readFile(path.join(output,'test-cert.pem'))} }, plugins: [{ name: 'real-unified-gateway',
    configureServer(server) {
      for (const [route, modulePath] of [['/api/unified', '/api/unified.ts'], ['/api/engineering-session', '/api/engineering-session.ts'], ['/api/code', '/api/code.ts']]) {
        server.middlewares.use(route, async (req, res, next) => {
          try { const module = await server.ssrLoadModule(modulePath); await module.default(req, res) } catch (e) { next(e) }
        })
      }
    } }] })
  await vite.listen()
  browser = await chromium.launch({ executablePath: '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] })
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1440, height: 1000 } })
  const anonymous = await context.request.get('https://localhost:5173/api/unified')
  const anonymousStatus = anonymous.status()
  if (anonymousStatus !== 200) throw Error('Active demonstration unexpectedly requires user sign-in')
  if ((await context.request.post('https://localhost:5173/api/code?action=run')).status() !== 410) throw Error('Retired operations endpoint still active')
  page = await context.newPage();const errors = []
  page.on('pageerror', error => errors.push(String(error)))
  page.on('response', async response => {if(response.url().includes('/api/unified'))console.log('gateway response', response.status(), response.status()>=400?await response.text().catch(()=> 'closed'):'ok')})
  await page.route('**/context-suggestions', route => route.fulfill({ status: 503, json: { detail: 'Offline browser replay; no Gemini calls' } }))
  await page.goto('https://localhost:5173')
  await page.evaluate(async () => {
    const { db } = await import('/src/db/database.ts')
    const now = new Date().toISOString()
    await db.projects.put({ id: 'e2e-project', name: 'Recorded CCTV engineering test', createdAt: now, updatedAt: now })
    await db.manholes.put({ id: 'e2e-manhole', projectId: 'e2e-project', manholeId: 'REPLAY', type: 'foul-water', pipeType: '300mm-concrete', pipeDiameterMm: 300,
      meterRun: 1, unitLengthM: 2.6, estimatedPipeCount: 1, estimatedJointCount: 1, createdAt: now, updatedAt: now })
  })
  await page.goto('https://localhost:5173/projects/e2e-project/manholes/e2e-manhole/upload')
  await page.locator('label').filter({hasText: 'Unified AI engineering preview'}).locator('input').check()
  await page.locator('#upload-input').setInputFiles({ name: 'real-frame-10.jpg', mimeType: 'image/jpeg', buffer: await fs.readFile(path.join(root, 'original.jpg')) })
  await page.waitForFunction(async () => { const {db} = await import('/src/db/database.ts');return (await db.inspectionImages.count()) > 0 })
  await page.locator('label').filter({hasText: 'Unified AI engineering preview'}).locator('input').check()
  await page.getByRole('button', {name: /Start inspection/i}).last().click()
  await page.getByRole('heading', {name: 'Unified AI engineering preview'}).waitFor({timeout: 30000})
  const results = await page.evaluate(async () => {const {db} = await import('/src/db/database.ts');return db.inspectionResults.toArray()})
  if (results.length !== 1 || results[0].executionSource !== 'CLOUD_RESEARCH_UNVERIFIED' || !results[0].unifiedEvidence?.replay_only || results[0].finalGapMm !== null) throw Error('Research evidence persistence failed')
  const exports = await page.evaluate(async () => { const {exportService} = await import('/src/services/exportService.ts');
    const json = await (await exportService.exportJson('e2e-project')).text();const pdf=await exportService.exportPdf('e2e-project');const zip=await exportService.exportEvidenceZip('e2e-project');
    return {json:JSON.parse(json), pdfBytes:pdf.size, zipBytes:zip.size} })
  if (!exports.json.results[0].unifiedEvidence || exports.pdfBytes < 1000 || exports.zipBytes < 1000) throw Error('Unified exports lost evidence')
  for (const width of [1440, 390]) {await page.setViewportSize({width, height:1000});await page.screenshot({path:path.join(output, `site-${width}.png`),fullPage:true})}
  await fs.writeFile(path.join(output, 'verification.json'), JSON.stringify({mode:'RECORDED_REAL_ARTIFACT_HTTP_REPLAY_NOT_LIVE_INFERENCE', anonymousStatus, userSignInRequired:false, retiredOperationsStatus:410,
    persistedResults:results.length, unifiedImageSha:results[0].unifiedEvidence.image_sha256, pdfBytes:exports.pdfBytes, zipBytes:exports.zipBytes, browserErrors:errors}, null, 2))
  if (errors.length) throw Error('Browser errors: '+errors.join(';'))
  console.log('Existing website upload → protected gateway → FastAPI replay → IndexedDB result → JSON/PDF/evidence ZIP verified.')
} catch(error) {if(page){await fs.writeFile(path.join(output,'failure.txt'),await page.locator('body').innerText());await page.screenshot({path:path.join(output,'failure.png'),fullPage:true})}throw error} finally {if(browser)await browser.close();if(vite)await vite.close();child.kill();globalThis.fetch=nativeFetch;await fs.writeFile(path.join(output,'backend.log'),log)}
