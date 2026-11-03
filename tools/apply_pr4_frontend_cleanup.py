from pathlib import Path

ROOT = Path.cwd()


def patch(path: str, old: str, new: str, count: int = 1) -> None:
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'Expected block not found in {path}: {old[:200]!r}')
    p.write_text(text.replace(old, new, count), encoding='utf-8')
    print('patched', path)


def patch_all(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'Expected block not found in {path}: {old[:200]!r}')
    p.write_text(text.replace(old, new), encoding='utf-8')
    print('patched all', path)

# CodeOperationsPage: defer the initial async refresh calls out of the effect
# body, so effects subscribe/schedule rather than synchronously triggering state
# updates through the called async functions.
patch(
    'src/pages/CodeOperationsPage.tsx',
    '''  useEffect(() => {\n    void refresh();\n    const timer = window.setInterval(() => void refresh(), 30000);\n    return () => window.clearInterval(timer);\n  }, [refresh]);''',
    '''  useEffect(() => {\n    const initial = window.setTimeout(() => void refresh(), 0);\n    const timer = window.setInterval(() => void refresh(), 30000);\n    return () => {\n      window.clearTimeout(initial);\n      window.clearInterval(timer);\n    };\n  }, [refresh]);''',
)
patch(
    'src/pages/CodeOperationsPage.tsx',
    '''  useEffect(() => {\n    if (authorized && view === "logs") {\n      void loadLogs();\n      const timer = window.setInterval(() => void loadLogs(), 15000);\n      return () => window.clearInterval(timer);\n    }\n  }, [authorized, view, loadLogs]);''',
    '''  useEffect(() => {\n    if (authorized && view === "logs") {\n      const initial = window.setTimeout(() => void loadLogs(), 0);\n      const timer = window.setInterval(() => void loadLogs(), 15000);\n      return () => {\n        window.clearTimeout(initial);\n        window.clearInterval(timer);\n      };\n    }\n  }, [authorized, view, loadLogs]);''',
)
patch(
    'src/pages/CodeOperationsPage.tsx',
    '''      save(\n        `jointinspect-gcp-report-${Date.now()}.json`,\n        JSON.stringify(data, null, 2),\n        "application/json",\n      );''',
    '''      save(\n        "jointinspect-gcp-report.json",\n        JSON.stringify(data, null, 2),\n        "application/json",\n      );''',
)

# Remove fake sample-image plumbing. The previous code created text blobs with a
# JPEG MIME type, which guaranteed decode failures and looked like a broken CV
# pipeline rather than sample data.
patch('src/pages/PhotoUploadPage.tsx', '  onLoadSample: () => Promise<void>\n', '')
patch('src/pages/PhotoUploadPage.tsx', '  onLoadSample,\n', '')
patch(
    'src/pages/PhotoUploadPage.tsx',
    '''              <button className="button button-secondary" type="button" onClick={() => void onLoadSample()} disabled={busy}>\n                Load Sample\n              </button>\n''',
    '',
)
patch(
    'src/App.tsx',
    '''          onLoadSample={async () => {\n            const sampleFiles = [\n              new File(['sample-one'], 'joint_1-2.jpg', { type: 'image/jpeg' }),\n              new File(['sample-two'], 'joint_2-3.jpg', { type: 'image/jpeg' }),\n              new File(['sample-three'], 'joint_3-4.jpg', { type: 'image/jpeg' }),\n            ]\n            await inspectionQueue.addFiles({\n              projectId: uploadProjectId,\n              manholeId: uploadManholeId,\n              files: sampleFiles,\n            })\n            await refreshRouteData()\n          }}\n''',
    '',
)

# Remove development console output from production navigation/processing paths.
patch_all('src/App.tsx', "        console.log('ROUTE INSPECTION ID:', route.inspectionId)\n", '')
patch_all('src/App.tsx', "          console.log('LOADED RESULTS:', enrichedResults)\n", '')
patch_all('src/App.tsx', "            console.log('PROCESS RESULT:', result)\n", '')

print('PR4 frontend cleanup applied')
