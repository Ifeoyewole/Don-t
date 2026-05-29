# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: accuracy-validation.spec.cjs >> accuracy validation sample sweep
- Location: tests\accuracy-validation.spec.cjs:65:1

# Error details

```
TimeoutError: page.waitForURL: Timeout 60000ms exceeded.
=========================== logs ===========================
waiting for navigation until "load"
============================================================
```

# Page snapshot

```yaml
- generic [ref=e3]:
  - banner [ref=e4]:
    - button "JointInspect" [ref=e5] [cursor=pointer]:
      - img "JointInspect" [ref=e6]
    - navigation "Primary" [ref=e7]:
      - button "Dashboard" [ref=e8] [cursor=pointer]
      - button "Projects" [ref=e9] [cursor=pointer]
    - generic [ref=e10]:
      - generic [ref=e13]: Online
      - button "Sync status" [ref=e14] [cursor=pointer]:
        - img [ref=e16]
      - generic [ref=e19]: JD
  - main [ref=e20]:
    - generic [ref=e21]:
      - generic [ref=e22]:
        - button "Projects" [ref=e23] [cursor=pointer]
        - generic [ref=e24]: ›
        - generic [ref=e25]: Accuracy Validation
        - generic [ref=e26]: ›
        - strong [ref=e27]: Evidence Upload
      - generic [ref=e28]:
        - generic [ref=e29]:
          - heading "Upload Inspection Evidence" [level=1] [ref=e30]
          - paragraph [ref=e31]: Ensure each joint is clearly visible. Upload photos in order so the app can measure each gap and assign a tolerance status.
        - button "Start Inspection" [ref=e32] [cursor=pointer]
      - generic [ref=e33]:
        - complementary [ref=e34]:
          - generic [ref=e35]:
            - button "Drag photos here Or click to browse your workstation. Support JPG, PNG up to 25MB. Photos only Upload order kept" [ref=e36]
            - generic [ref=e37]:
              - generic [ref=e38]: ⌁
              - strong [ref=e39]: Drag photos here
              - generic [ref=e40]: Or click to browse your workstation. Support JPG, PNG up to 25MB.
              - generic [ref=e41]:
                - generic [ref=e42]: Photos only
                - generic [ref=e43]: Upload order kept
          - generic [ref=e44]:
            - generic [ref=e45]:
              - strong [ref=e46]: Inspection Run
              - generic [ref=e47]: Ready
            - generic [ref=e48]:
              - generic [ref=e49]: Reported device link
              - strong [ref=e50]: 9.1 Mbps
            - paragraph [ref=e53]: Project data stays on this device, and queued photos keep their upload order while you work.
            - paragraph [ref=e54]: All queued photos are eligible for measurement.
            - generic [ref=e55]:
              - button "Load Sample" [ref=e56] [cursor=pointer]
              - button "Clear All" [ref=e57] [cursor=pointer]
        - generic [ref=e58]:
          - generic [ref=e59]:
            - generic [ref=e60]:
              - heading "Uploaded Assets" [level=2] [ref=e61]
              - generic [ref=e62]: 1 Files
            - generic [ref=e63]:
              - generic [ref=e64]: ◫
              - generic [ref=e65]: ☰
          - paragraph [ref=e66]: Inspection processing failed
          - article [ref=e68]:
            - generic [ref=e69]:
              - img "test 1.jpeg" [ref=e70]
              - button "Remove" [ref=e71] [cursor=pointer]
            - generic [ref=e72]:
              - generic [ref=e73]:
                - strong [ref=e74]: test 1.jpeg
                - generic [ref=e75]: 1-2
              - generic [ref=e76]:
                - generic [ref=e77]: Failed
                - generic [ref=e78]: MH-VAL-01
              - generic [ref=e80]: Needs retake
              - paragraph [ref=e83]: "Retake photo: keep the pipe opening centered and make the full joint ring edge visible."
              - paragraph [ref=e84]: "Retake photo: the pipe opening is not clear enough for reliable gap measurement."
          - generic [ref=e85]:
            - generic [ref=e86]: Showing 1 of 1 assets for current inspection run.
            - generic [ref=e87]:
              - button "Clear all" [ref=e88] [cursor=pointer]
              - button "Start Inspection" [ref=e89] [cursor=pointer]
      - generic [ref=e90]:
        - generic [ref=e92]:
          - heading "Processing Feed" [level=2] [ref=e93]
          - paragraph [ref=e94]: 0 item(s) completed in the current run.
        - generic [ref=e95]:
          - paragraph [ref=e96]: "[FAILED] Retake photo: keep the pipe opening centered and make the full joint ring edge visible."
          - paragraph [ref=e97]: "[PROGRESS] 60% Running enhanced CV and AI review"
          - paragraph [ref=e98]: "[PROGRESS] 25% Preparing image"
          - paragraph [ref=e99]: "[STARTED] 1bd5ed1e-c56f-4bb6-beb7-3fd27e819d85"
```

# Test source

```ts
  1  | const { test } = require('@playwright/test')
  2  | const path = require('node:path')
  3  | 
  4  | const root = path.resolve(__dirname, '..')
  5  | const publicDir = path.join(root, 'public')
  6  | 
  7  | async function bootstrapProject(page) {
  8  |   await page.goto('/', { waitUntil: 'networkidle' })
  9  |   await page.getByRole('button', { name: 'New Project' }).click()
  10 |   await page.getByLabel('Project Name').fill('Accuracy Validation')
  11 |   await page.getByLabel('Site Name').fill('Validation Site')
  12 |   await page.getByRole('button', { name: 'Save Project' }).click()
  13 |   await page.waitForURL(/\/manholes\/new$/, { timeout: 15000 })
  14 |   await page.getByLabel('Manhole ID').fill('MH-VAL-01')
  15 |   await page.getByLabel('Meter Run').fill('18')
  16 |   await page.getByRole('button', { name: 'Save Manhole' }).click()
  17 |   await page.waitForURL(/\/upload$/, { timeout: 15000 })
  18 | }
  19 | 
  20 | async function clearQueue(page) {
  21 |   const clearButtons = page.getByRole('button', { name: 'Clear all' })
  22 |   const count = await clearButtons.count()
  23 |   if (count) {
  24 |     await clearButtons.nth(count - 1).click()
  25 |   }
  26 | }
  27 | 
  28 | async function measureImage(page, fileName) {
  29 |   await page.locator('#upload-input').setInputFiles([path.join(publicDir, fileName)])
  30 | 
  31 |   const startButtons = page.getByRole('button', { name: 'Start Inspection' })
  32 |   const startButton = startButtons.nth((await startButtons.count()) - 1)
  33 |   const startDisabled = await startButton.isDisabled()
  34 | 
  35 |   if (startDisabled) {
  36 |     const retakeBadge = await page.locator('.mini-status-pill, .asset-validation-row').textContent().catch(() => '')
  37 |     const retakeReason = await page.locator('.asset-validation-message').textContent().catch(() => '')
  38 |     console.log(`ACCURACY_CASE=${JSON.stringify({ fileName, outcome: 'retake', retakeBadge, retakeReason })}`)
  39 |     await clearQueue(page)
  40 |     return
  41 |   }
  42 | 
  43 |   await startButton.click()
> 44 |   await page.waitForURL(/\/results$/, { timeout: 60000 })
     |              ^ TimeoutError: page.waitForURL: Timeout 60000ms exceeded.
  45 | 
  46 |   const card = page.locator('.inspection-result-card').first()
  47 |   const gap = await card.locator('.inspection-gap-row').first().locator('strong').textContent()
  48 |   const status = await card.locator('.inspection-gap-row').nth(1).locator('strong').textContent()
  49 |   const meta = await card.locator('.inspection-meta-row').textContent()
  50 | 
  51 |   console.log(
  52 |     `ACCURACY_CASE=${JSON.stringify({
  53 |       fileName,
  54 |       outcome: 'measured',
  55 |       gap,
  56 |       status,
  57 |       meta,
  58 |     })}`,
  59 |   )
  60 | 
  61 |   await page.goto(page.url().replace(/\/results$/, '/upload'), { waitUntil: 'networkidle' })
  62 |   await clearQueue(page)
  63 | }
  64 | 
  65 | test('accuracy validation sample sweep', async ({ page }) => {
  66 |   page.on('console', (message) => {
  67 |     const text = message.text()
  68 |     if (text.startsWith('[cv-worker]')) {
  69 |       console.log(`WORKER_TRACE=${text}`)
  70 |     }
  71 |   })
  72 | 
  73 |   await bootstrapProject(page)
  74 | 
  75 |   for (const fileName of ['test 1.jpeg', 'test 2.jpeg', 'test 3.jpeg', 'test 4.jpeg', 'test 5.jpeg', 'test 6.jpeg', 'test 7.jpeg']) {
  76 |     await measureImage(page, fileName)
  77 |   }
  78 | })
  79 | 
```