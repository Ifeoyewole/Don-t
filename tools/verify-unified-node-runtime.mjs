/** Reproduce Vercel's emitted ESM loading without Vite's import resolver. */
import { spawnSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const temporaryRoot = path.join(root, 'node_modules', '.tmp')
mkdirSync(temporaryRoot, { recursive: true })
const output = mkdtempSync(path.join(temporaryRoot, 'unified-native-esm-'))
function run(args, env = process.env) {
  const result = spawnSync(process.execPath, args, { cwd: root, env, stdio: 'inherit' })
  if (result.status !== 0) throw new Error('Native gateway runtime regression failed')
}
try {
  run(['node_modules/typescript/bin/tsc', '-p', 'api/tsconfig.json', '--noEmit', 'false',
    '--allowImportingTsExtensions', 'false', '--outDir', output])
  writeFileSync(path.join(output, 'package.json'), JSON.stringify({ type: 'module' }))
  run(['--input-type=module', '--eval', `
    import { pathToFileURL } from 'node:url';
    const {default: handler} = await import(pathToFileURL(process.argv[1]).href);
    async function invoke() {
      let status = 0;
      await handler({method:'GET',headers:{}},{writeHead:s=>{status=s},end:()=>{}});
      return status;
    }
    if (await invoke() !== 404) throw new Error('Disabled preview must return 404');
    process.env.UNIFIED_ENGINEERING_PREVIEW_ENABLED='true';
    if (await invoke() !== 401) throw new Error('Anonymous preview must return 401');
    console.log('Native emitted ESM gateway: disabled=404, anonymous=401');
  `, path.join(output, 'unified.js')], { ...process.env,
    UNIFIED_ENGINEERING_PREVIEW_ENABLED: 'false', UNIFIED_PREVIEW_EXPIRES_UNIX: '' })
} finally {
  rmSync(output, { recursive: true, force: true })
}
