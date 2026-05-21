import { chromium } from 'playwright'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const distDir = path.join(root, 'dist')
const publicDir = path.join(root, 'public')

const mimeTypes = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.jpeg': 'image/jpeg',
  '.jpg': 'image/jpeg',
  '.png': 'image/png',
  '.json': 'application/json; charset=utf-8',
}

async function getFileResponse(urlPath) {
  const normalized = urlPath === '/' ? '/index.html' : urlPath
  const diskPath = path.join(distDir, normalized.replace(/^\//, ''))

  try {
    const body = await fs.readFile(diskPath)
    const ext = path.extname(diskPath).toLowerCase()
    return {
      status: 200,
      contentType: mimeTypes[ext] ?? 'application/octet-stream',
      body,
    }
  } catch {
    if (normalized.startsWith('/test ')) {
      const publicPath = path.join(publicDir, normalized.replace(/^\//, ''))
      const body = await fs.readFile(publicPath)
      const ext = path.extname(publicPath).toLowerCase()
      return {
        status: 200,
        contentType: mimeTypes[ext] ?? 'application/octet-stream',
        body,
      }
    }

    const fallback = await fs.readFile(path.join(distDir, 'index.html'))
    return {
      status: 200,
      contentType: 'text/html; charset=utf-8',
      body: fallback,
    }
  }
}

async function run() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } })

  await page.route('http://app.local/**', async (route) => {
    const requestUrl = new URL(route.request().url())
    const response = await getFileResponse(requestUrl.pathname)
    await route.fulfill(response)
  })

  await page.goto('http://app.local/', { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'New Project' }).click()
  await page.getByLabel('Project Name').fill('Measurement Validation')
  await page.getByLabel('Site Name / ID').fill('Validation Site')
  await page.getByRole('button', { name: 'Save Project' }).click()
  await page.waitForURL(/\/upload$/, { timeout: 15000 })

  const uploadInput = page.locator('#upload-input')

  const runCase = async (name, fileNames) => {
    await uploadInput.setInputFiles(fileNames.map((fileName) => path.join(publicDir, fileName)))
    await page.getByRole('button', { name: 'Start Inspection' }).click()
    await page.waitForURL(/\/results$/, { timeout: 45000 })
    const resultCards = page.locator('.inspection-result-card')
    const count = await resultCards.count()
    const results = []

    for (let index = 0; index < count; index += 1) {
      const card = resultCards.nth(index)
      results.push({
        joint: await card.locator('.result-media-bottom strong').textContent(),
        gap: await card.locator('.inspection-gap-row strong').textContent(),
        meta: await card.locator('.inspection-meta-row').textContent(),
      })
    }

    console.log(`CASE ${name}`)
    console.log(JSON.stringify(results, null, 2))

    await page.goto(page.url().replace(/\/results$/, '/upload'), { waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Clear all' }).click()
  }

  await runCase('test-2-3', ['test 2.jpeg', 'test 3.jpeg'])
  await runCase('test-6', ['test 6.jpeg'])

  await browser.close()
}

run().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
