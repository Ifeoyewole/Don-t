# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: measurement-validation.spec.cjs >> measurement validation samples
- Location: tests\measurement-validation.spec.cjs:74:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('Needs retake')
Expected: visible
Timeout: 15000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 15000ms
  - waiting for getByText('Needs retake')

```

```yaml
- banner:
  - button "JointInspect":
    - img "JointInspect"
  - navigation "Primary":
    - button "Dashboard"
    - button "Projects"
  - text: Online
  - button "Sync status"
- main:
  - button "Projects"
  - text: › Measurement Validation ›
  - strong: Evidence Upload
  - heading "Upload Inspection Evidence" [level=1]
  - paragraph: Ensure each joint is clearly visible. Upload photos in order so the app can measure each gap and assign a tolerance status.
  - button "Start Inspection"
  - complementary:
    - button "Drag photos here Or click to browse your workstation. Support JPG, PNG up to 25MB. Photos only Upload order kept"
    - strong: Drag photos here
    - text: Or click to browse your workstation. Support JPG, PNG up to 25MB. Photos only Upload order kept
    - strong: Inspection Run
    - text: Ready Reported device link
    - strong: 9.4 Mbps
    - paragraph: Project data stays on this device, and queued photos keep their upload order while you work.
    - paragraph: 1 photo(s) will use enhanced CV and AI review before a retake decision.
    - button "Load Sample"
    - button "Clear All"
  - heading "Uploaded Assets" [level=2]
  - text: 1 Files
  - article:
    - img "test 6.jpeg"
    - button "Remove"
    - strong: test 6.jpeg
    - text: 1-2 Queued MH-TEST-01 AI review needed
    - paragraph: 0% complete
    - paragraph: "Retake photo: use the guided capture angle and keep the full pipe opening steady in frame."
  - text: Showing 1 of 1 assets for current inspection run.
  - button "Clear all"
  - button "Start Inspection"
  - heading "Processing Feed" [level=2]
  - paragraph: 0 item(s) completed in the current run.
  - paragraph: Waiting for queue activity.
```

# Test source

```ts
  4   | const root = path.resolve(__dirname, '..')
  5   | const publicDir = path.join(root, 'public')
  6   | 
  7   | async function bootstrapProject(page) {
  8   |   await page.goto('/', { waitUntil: 'networkidle' })
  9   |   await page.getByRole('button', { name: 'New Project' }).click()
  10  |   await page.getByLabel('Project Name').fill('Measurement Validation')
  11  |   await page.getByLabel('Site Name').fill('Validation Site')
  12  |   await page.getByRole('button', { name: 'Save Project' }).click()
  13  |   await page.waitForURL(/\/manholes\/new$/, { timeout: 15000 })
  14  |   await page.getByLabel('Manhole ID').fill('MH-TEST-01')
  15  |   await page.getByLabel('Meter Run').fill('18')
  16  |   await page.getByRole('button', { name: 'Save Manhole' }).click()
  17  |   await page.waitForURL(/\/upload$/, { timeout: 15000 })
  18  | }
  19  | 
  20  | async function collectResults(page) {
  21  |   const cards = page.locator('.inspection-result-card')
  22  |   const count = await cards.count()
  23  |   const results = []
  24  | 
  25  |   for (let index = 0; index < count; index += 1) {
  26  |     const card = cards.nth(index)
  27  |     results.push({
  28  |       joint: await card.locator('.result-media-bottom strong').textContent(),
  29  |       gap: await card.locator('.inspection-gap-row').first().locator('strong').textContent(),
  30  |       meta: await card.locator('.inspection-meta-row').textContent(),
  31  |     })
  32  |   }
  33  | 
  34  |   return results
  35  | }
  36  | 
  37  | async function processSingleImage(page, fileName) {
  38  |   const uploadInput = page.locator('#upload-input')
  39  |   await uploadInput.setInputFiles([path.join(publicDir, fileName)])
  40  |   await page.getByRole('button', { name: 'Start Inspection' }).nth(1).click()
  41  |   await page.waitForURL(/\/results$/, { timeout: 60000 })
  42  |   const hasResults = await page.locator('.inspection-result-card').first().isVisible({ timeout: 15000 }).catch(() => false)
  43  |   const dbState = await page.evaluate(async () => {
  44  |     const database = await new Promise((resolve, reject) => {
  45  |       const request = indexedDB.open('pipe-joint-inspection-db')
  46  |       request.onerror = () => reject(request.error)
  47  |       request.onsuccess = () => resolve(request.result)
  48  |     })
  49  | 
  50  |     const readAll = (storeName) =>
  51  |       new Promise((resolve, reject) => {
  52  |         const transaction = database.transaction(storeName, 'readonly')
  53  |         const store = transaction.objectStore(storeName)
  54  |         const request = store.getAll()
  55  |         request.onerror = () => reject(request.error)
  56  |         request.onsuccess = () => resolve(request.result)
  57  |       })
  58  | 
  59  |     return {
  60  |       images: await readAll('inspectionImages'),
  61  |       results: await readAll('inspectionResults'),
  62  |     }
  63  |   })
  64  |   console.log(`DB_STATE_${fileName.toUpperCase().replace(/[^A-Z0-9]+/g, '_')}=${JSON.stringify(dbState)}`)
  65  |   if (!hasResults) {
  66  |     return []
  67  |   }
  68  |   const results = await collectResults(page)
  69  |   await page.goto(page.url().replace(/\/results$/, '/upload'), { waitUntil: 'networkidle' })
  70  |   await page.getByRole('button', { name: 'Clear all' }).nth(1).click()
  71  |   return results
  72  | }
  73  | 
  74  | test('measurement validation samples', async ({ page }) => {
  75  |   page.on('console', (message) => {
  76  |     console.log(`BROWSER_${message.type().toUpperCase()}=${message.text()}`)
  77  |   })
  78  | 
  79  |   await page.addInitScript(() => {
  80  |     if (!globalThis.crypto) {
  81  |       globalThis.crypto = {}
  82  |     }
  83  |     if (typeof globalThis.crypto.randomUUID !== 'function') {
  84  |       globalThis.crypto.randomUUID = () =>
  85  |         'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (token) => {
  86  |           const value = Math.floor(Math.random() * 16)
  87  |           const variant = token === 'x' ? value : (value & 0x3) | 0x8
  88  |           return variant.toString(16)
  89  |         })
  90  |     }
  91  |   })
  92  | 
  93  |   await bootstrapProject(page)
  94  |   const test2Results = await processSingleImage(page, 'test 2.jpeg')
  95  |   console.log(`TEST2_RESULTS=${JSON.stringify(test2Results)}`)
  96  |   expect(test2Results.length).toBeGreaterThan(0)
  97  | 
  98  |   const test3Results = await processSingleImage(page, 'test 3.jpeg')
  99  |   console.log(`TEST3_RESULTS=${JSON.stringify(test3Results)}`)
  100 |   expect(test3Results.length).toBeGreaterThan(0)
  101 | 
  102 |   const uploadInput = page.locator('#upload-input')
  103 |   await uploadInput.setInputFiles([path.join(publicDir, 'test 6.jpeg')])
> 104 |   await expect(page.getByText('Needs retake')).toBeVisible({ timeout: 15000 })
      |                                                ^ Error: expect(locator).toBeVisible() failed
  105 | })
  106 | 
```